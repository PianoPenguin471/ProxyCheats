import json
import logging
import sys
from quarry.types.chat import Message
import customtkinter
import mojang
from mojang import LoginFailure
from quarry.net.ticker import Ticker

from modules import NoWeather, Xray, Module, Blink, Packet
import requests
from quarry.net.protocol import ProtocolError
from quarry.types.buffer import Buffer, Buffer1_7
from twisted.python import failure

from quarry.types.uuid import UUID
from quarry.net.proxy import UpstreamFactory, Upstream, DownstreamFactory, Downstream, Bridge
from quarry.net import auth, crypto
from twisted.internet import reactor

ACCESS_TOKEN = ''
SERVER_IP = "test.karhu.ac" #input("Server Ip: ")
SERVER_PORT = 25565

no_weather: NoWeather = None
xray: Xray = None
blink: Blink = None
has_initialized_modules: bool = False

ticker: Ticker = Ticker(logger=logging.Logger("tick_event"))


def send_message_to_client(downstream: Downstream, message_str: str):
    print(message_str)


class MyUpstream(Upstream):
    def packet_login_encryption_request(self, buff):
        Module.upstream = self
        p_server_id = buff.unpack_string()

        # 1.7.x
        if self.protocol_version <= 5:
            def unpack_array(b):
                return b.read(b.unpack('h'))
        # 1.8.x
        else:
            def unpack_array(b):
                return b.read(b.unpack_varint(max_bits=16))

        p_public_key = unpack_array(buff)
        p_verify_token = unpack_array(buff)

        if not self.factory.profile.online:
            raise ProtocolError("Can't log into online-mode server while using"
                                " offline profile")

        self.shared_secret = crypto.make_shared_secret()
        self.public_key = crypto.import_public_key(p_public_key)
        self.verify_token = p_verify_token

        # make digest
        digest = crypto.make_digest(
            p_server_id.encode('ascii'),
            self.shared_secret,
            p_public_key)

        # do auth
        # deferred = self.factory.profile.join(digest)
        # deferred.addCallbacks(self.auth_ok, self.auth_failed)

        url = "https://sessionserver.mojang.com/session/minecraft/join"

        payload = json.dumps({
            "accessToken": self.factory.profile.access_token,
            "selectedProfile": self.factory.profile.uuid.to_hex(False),
            "serverId": digest
        })
        headers = {
            'Content-Type': 'application/json'
        }

        r = requests.request(
            "POST", "https://sessionserver.mojang.com/session/minecraft/join", headers=headers, data=payload)

        if r.status_code == 204:
            self.auth_ok(r.text)
        else:
            self.auth_failed(failure.Failure(
                auth.AuthException('unverified', 'unverified username')))


class MyDownstream(Downstream):
    def packet_login_encryption_response(self, buff):
        Module.downstream = self
        if self.login_expecting != 1:
            raise ProtocolError("Out-of-order login")

        # 1.7.x
        if self.protocol_version <= 5:
            def unpack_array(b):
                return b.read(b.unpack('h'))
        # 1.8.x
        else:
            def unpack_array(b):
                return b.read(b.unpack_varint(max_bits=16))

        p_shared_secret = unpack_array(buff)
        p_verify_token = unpack_array(buff)

        shared_secret = crypto.decrypt_secret(
            self.factory.keypair,
            p_shared_secret)

        verify_token = crypto.decrypt_secret(
            self.factory.keypair,
            p_verify_token)

        self.login_expecting = None

        if verify_token != self.verify_token:
            raise ProtocolError("Verify token incorrect")

        # enable encryption
        self.cipher.enable(shared_secret)
        self.logger.debug("Encryption enabled")

        # make digest
        digest = crypto.make_digest(
            self.server_id.encode('ascii'),
            shared_secret,
            self.factory.public_key)

        # do auth
        remote_host = None
        if self.factory.prevent_proxy_connections:
            remote_host = self.remote_addr.host

        # deferred = auth.has_joined(
        #     self.factory.auth_timeout,
        #     digest,
        #     self.display_name,
        #     remote_host)
        # deferred.addCallbacks(self.auth_ok, self.auth_failed)

        r = requests.get('https://sessionserver.mojang.com/session/minecraft/hasJoined',
                         params={'username': self.display_name, 'serverId': digest, 'ip': remote_host})

        if r.status_code == 200:
            self.auth_ok(r.json())
        else:
            self.auth_failed(failure.Failure(
                auth.AuthException('invalid', 'invalid session')))


class MyUpstreamFactory(UpstreamFactory):
    protocol = MyUpstream

    connection_timeout = 10


class MyBridge(Bridge):
    upstream_factory_class = MyUpstreamFactory

    def packet_downstream_game_event(self, buff: Buffer1_7):
        # https://wiki.vg/Protocol#Game_Event
        event = buff.read(1)
        print(event)
        if no_weather.on_game_event(buff, event): return
        if event == 0:
            print("No spawnpoint")
        elif event == 1:
            print("End raining")
        elif event == 2:
            print("Start raining")
        elif event == 6:
            print("Arrow hit")
        elif event == 11:
            print("Immediate respawn changed")

        buff.restore()
        self.downstream.send_packet("game_event", buff.read())

    def packet_received(self, buff, direction, name):
        global has_initialized_modules, no_weather, xray, blink
        if not has_initialized_modules:
            has_initialized_modules = True
            print(self.downstream)
            no_weather = NoWeather(self.downstream, self.upstream)
            xray = Xray(self.downstream, self.upstream)
            blink = Blink(self.downstream, self.upstream)

        if blink.enabled and not "chat" in name:
            blink.packet_list.append(Packet(name, buff.read(), direction))
            return
        super().packet_received(buff, direction, name)

    def packet_downstream_chat_message(self, buff: Buffer1_7):
        buff.save()

        message: Message = buff.unpack_chat()
        print(message.to_string(False))

        buff.restore()
        self.downstream.send_packet("chat_message", buff.read())

    def packet_upstream_chat_message(self, buff: Buffer1_7):
        buff.save()
        try:
            chat_message = buff.unpack_string()

            if chat_message.startswith("."):
                cmd = chat_message.split(" ")[0][1:]
                args = chat_message.split(" ")[1:]
                if "toggle" in cmd:
                    global xray, no_weather, blink
                    module: str = args[0]
                    if "xray" in module.lower():
                        xray.toggle()
                        send_message_to_client(self.downstream, f"Xray toggled: {xray.enabled}")
                    elif "noweather" in module.lower():
                        no_weather.toggle()
                        send_message_to_client(self.downstream, f"No-Weather toggled: {no_weather.enabled}")
                    elif "blink" in module.lower():
                        blink.toggle()
                        send_message_to_client(self.downstream, f"Blink toggled: {blink.enabled}")
            else:
                buff.restore()
                self.upstream.send_packet("chat_message", buff.read())
        except Exception as e:
            print(e)

    def make_profile(self):
        """
        Support online mode
        """
        print("Making Profile")
        local_path = '/'.join(sys.argv[0].split("\\")[:-1])
        try:
            with open(local_path + "/TOKEN", "w+") as f:
                client = mojang.Client(bearer_token=f.readline())
                print("Logged In Successfully")
                return auth.Profile("(skip)", client.bearer_token, client.get_profile().name,
                                    UUID.from_hex(client.get_profile().id))
        except LoginFailure:
            print("Invalid Token, Please log in again.")
            root = customtkinter.CTk()

            email_entry = customtkinter.CTkEntry(master=root, placeholder_text="Microsoft Email")
            email_entry.grid(row=0, column=0, padx=20, pady=10)

            password_entry = customtkinter.CTkEntry(master=root, placeholder_text="Microsoft Password", show="*")
            password_entry.grid(row=1, column=0, padx=20, pady=10)

            def login_email_and_pass():
                new_client = mojang.Client(email=email_entry.get(), password=password_entry.get())
                with open(local_path + "/TOKEN", 'w') as file:
                    file.write(new_client.bearer_token)
                root.destroy()
                return auth.Profile("(skip)", new_client.bearer_token, new_client.get_profile().name,
                                    new_client.get_profile().id)

            login_button = customtkinter.CTkButton(master=root, text="Login", command=login_email_and_pass)
            login_button.grid(row=2, column=0, padx=20, pady=10)

            root.mainloop()


class MyDownstreamFactory(DownstreamFactory):
    protocol = MyDownstream
    bridge_class = MyBridge
    online_mode = False
    motd = f"Proxy Server for {SERVER_IP}:{SERVER_PORT}"


def main():
    global no_weather, xray, blink
    factory = MyDownstreamFactory()
    factory.connect_host = SERVER_IP
    factory.connect_port = SERVER_PORT

    # Listen
    factory.listen("", 25565)
    reactor.run()


if __name__ == "__main__":
    main()

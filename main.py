import json

import quarry.types.buffer
import requests
from quarry.net.protocol import ProtocolError
from quarry.types.buffer import Buffer, Buffer1_7
from requests import JSONDecodeError
from twisted.python import failure

from quarry.types.uuid import UUID
from quarry.net.proxy import UpstreamFactory, Upstream, DownstreamFactory, Downstream, Bridge
from quarry.net import auth, crypto
from twisted.internet import reactor

ACCESS_TOKEN = 'eyJhbGciOiJIUzI1NiJ9.eyJ4dWlkIjoiMjUzNTQxMDUxNTM2OTMwNSIsImFnZyI6IkFkdWx0Iiwic3ViIjoiNzM2OTM1NWItNzVjNy00ZmFjLTk2NGQtNTUxMmI1ZDc4NDEzIiwibmJmIjoxNjYyNDg4ODY5LCJhdXRoIjoiWEJPWCIsInJvbGVzIjpbXSwiaXNzIjoiYXV0aGVudGljYXRpb24iLCJleHAiOjE2NjI1NzUyNjksImlhdCI6MTY2MjQ4ODg2OSwicGxhdGZvcm0iOiJVTktOT1dOIiwieXVpZCI6IjcxZjgyYmI1ODI2NDY4OTA0M2JkMTQwYjkzYzgwNmZjIn0.XTQ7gRXOlcnzFqMGo7CpYUU1tZFX95S_FIiqQsJ2ym4'
SERVER_IP = "coldpvp.com"
SERVER_PORT = 25565
has_enabled_xray=False


class MyUpstream(Upstream):
    def packet_login_encryption_request(self, buff):
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
        buff.save()
        print(buff.unpack("B"))

    def packet_downstream_plugin_message(self, buff: Buffer):
        buff.save()
        channel = buff.unpack_string()
        print("Downstream channel: " + channel)
        buff.restore()
        print(buff.read())
        print()
        # print(buff.unpack_array(), end="\n\n\n")
        buff.restore()
        self.downstream.send_packet("plugin_message", buff.read())

    def packet_upstream_plugin_message(self, buff: Buffer):
        buff.save()
        channel = buff.unpack_string()
        print("Upstream channel: " + channel)
        buff.restore()
        print(buff.read())
        print()
        # print(buff.unpack_array(), end="\n\n\n")
        buff.restore()
        self.upstream.send_packet("plugin_message", buff.read())
        global has_enabled_xray
        # Todo send plugin message packet to turn on the X-ray staff module in lunar client
        """
        Lunar client code for the message
        public void write(ByteBufWrapper buf) throws IOException {
            buf.writeString(this.mod);
            buf.buf().writeBoolean(this.state);
        }   
        """
        """
        if "REGISTER" in channel and not has_enabled_xray:
            has_enabled_xray = True
            print("toggling xray")
            self.downstream.send_packet("plugin_message", self.buff_type.pack_string("lunarclient:pm") + self.buff_type.pack_string("XRAY") + self.buff_type.pack_optional(True))
        """


    def make_profile(self):
        """
        Support online mode
        """

        # follow: https://kqzz.github.io/mc-bearer-token/
        url = "https://api.minecraftservices.com/minecraft/profile"
        headers = {'Authorization': 'Bearer ' + ACCESS_TOKEN}
        response = requests.request("GET", url, headers=headers)
        try:
            result = response.json()
            myUuid = UUID.from_hex(result['id'])
            myUsername = result['name']
            return auth.Profile('(skip)', ACCESS_TOKEN, myUsername, myUuid)
        except JSONDecodeError as e:
            input("Invalid token, try again")
            exit()


class MyDownstreamFactory(DownstreamFactory):
    protocol = MyDownstream
    bridge_class = MyBridge
    motd = f"Proxy Server for {SERVER_IP}:{SERVER_PORT}"


def main(argv):
    # Parse options
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("-a1", "--listen-host1", default="",
                        help="address to listen on")
    parser.add_argument("-p1", "--listen-port1", default=25565,
                        type=int, help="port to listen on")
    args = parser.parse_args(argv)

    # Create factory
    factory = MyDownstreamFactory()
    factory.connect_host = SERVER_IP
    factory.connect_port = SERVER_PORT

    # Listen
    factory.listen(args.listen_host1, args.listen_port1)
    reactor.run()


if __name__ == "__main__":
    import sys

    main(sys.argv[1:])

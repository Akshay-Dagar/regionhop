import os

from regionhop.tunnel import Tunnel, _make_askpass


def test_key_command_has_identity():
    cmd = Tunnel(host="h", user="u", key_path="~/.ssh/k", port=1080)._build_command()
    assert "-i" in cmd
    assert "-D" in cmd
    assert "1080" in cmd
    assert "PubkeyAuthentication=no" not in " ".join(cmd)


def test_password_command_forces_password_auth():
    cmd = Tunnel(host="h", user="u", port=1080, password="pw")._build_command()
    joined = " ".join(cmd)
    assert "PubkeyAuthentication=no" in joined
    assert "PreferredAuthentications=password,keyboard-interactive" in joined
    assert "-i" not in cmd  # password auth doesn't use a key identity


def test_make_askpass_keeps_password_off_disk():
    path, env = _make_askpass("s3cr3t")
    try:
        content = open(path, encoding="utf-8", errors="replace").read()
        assert "s3cr3t" not in content  # password comes from the env, not the file
        assert env["REGIONHOP_ASKPASS_PW"] == "s3cr3t"
        assert env["SSH_ASKPASS"] == path
        assert env["SSH_ASKPASS_REQUIRE"] == "force"
    finally:
        os.remove(path)

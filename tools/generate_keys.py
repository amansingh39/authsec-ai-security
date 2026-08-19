"""
Generate RSA keypair + JWKS for Method B (Private-key JWT).
Outputs: private_key.pem, public_key.pem, jwks.json
Host jwks.json at a public URL and register it in AuthSec dashboard.
"""
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
import base64, json, os

OUT_DIR = os.path.join(os.path.dirname(__file__), "..")

key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

with open(os.path.join(OUT_DIR, "private_key.pem"), "wb") as f:
    f.write(key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ))

pub = key.public_key()
with open(os.path.join(OUT_DIR, "public_key.pem"), "wb") as f:
    f.write(pub.public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    ))

n = pub.public_numbers().n
e = pub.public_numbers().e
b64u = lambda i, length: base64.urlsafe_b64encode(
    i.to_bytes(length, "big")
).rstrip(b"=").decode()

jwks = {"keys": [{
    "kty": "RSA", "use": "sig", "alg": "RS256", "kid": "key-1",
    "n": b64u(n, (n.bit_length() + 7) // 8),
    "e": b64u(e, 3),
}]}

with open(os.path.join(OUT_DIR, "jwks.json"), "w") as f:
    json.dump(jwks, f, indent=2)

print("Generated:")
print(f"  private_key.pem  (keep secret)")
print(f"  public_key.pem")
print(f"  jwks.json        (host at a public URL)")

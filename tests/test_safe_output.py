import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from _safe_output import MASK, mask, secret_values


def test_secret_like_env_values_are_masked():
    env = {
        "HF_TOKEN": "hf_FAKEvalueForMaskTest",
        "KAGGLE_API_TOKEN": "KGAT_FAKE_value_for_mask_test",
        "MODAL_TOKEN_SECRET": "as-FAKE-value-for-mask-test",
        "HOME": "/home/user/somewhere-long",
        "SHORT_TOKEN": "abc",
    }
    secrets = secret_values(env)
    assert "/home/user/somewhere-long" not in secrets
    assert "abc" not in secrets
    text = f"auth {env['HF_TOKEN']} then {env['KAGGLE_API_TOKEN']} and {env['MODAL_TOKEN_SECRET']}"
    assert mask(text, secrets) == f"auth {MASK} then {MASK} and {MASK}"

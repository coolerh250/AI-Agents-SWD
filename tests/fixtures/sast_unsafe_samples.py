"""Step 54.2 -- intentional unsafe-pattern fixture for the local SAST baseline.

This file is EXCLUDED from the normal SAST target catalog (tests/fixtures). The
SAST verifier scans it EXPLICITLY to confirm the custom static checks detect each
unsafe pattern. The patterns live inside a raw string so importing this module
executes nothing -- the scanner reads it as TEXT.
"""

from __future__ import annotations

# Each line below is an intentional unsafe pattern the custom static checks flag.
UNSAFE_PATTERNS = r"""
subprocess.run(user_cmd, shell=True)
eval(user_supplied)
exec(payload_code)
yaml.load(untrusted_yaml)
requests.get(endpoint, verify=False)
app.run(host="0.0.0.0")
# TODO production bypass: disable auth before release
"""

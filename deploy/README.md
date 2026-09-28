# deploy/

Server configuration for the OCI VM this app shares with the scramble challenge app. Nothing
here holds an IP, OCID, SSH detail or secret; those stay in gitignored files on the VM.

The image carries a copy of this directory at `/opt/wca-records-analyser/deploy`, so the VM
installs it from the image rather than from a checkout. How to install and run it:
[`docs/runbook.md`](../docs/runbook.md).

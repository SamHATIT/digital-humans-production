# systemd unit templates — Doppler-wrapped

Drop-in templates for the migration described in
[`../../SECURITY.md`](../../SECURITY.md) §3. Copy each `*.service.example`
to `/etc/systemd/system/` (without the `.example` suffix), adjust the
hard-coded paths if needed, then `systemctl daemon-reload && systemctl
restart`.

| File | Replaces |
|------|----------|
| `digital-humans-backend.service.example` | `/etc/systemd/system/digital-humans-backend.service` |
| `digital-humans-worker.service.example` | `/etc/systemd/system/digital-humans-worker.service` |
| `digital-humans-frontend.service.example` | `/etc/systemd/system/digital-humans-frontend.service` |

Each unit reads `DOPPLER_TOKEN` from `/etc/digital-humans/doppler.env`
(provisioned in §3 step 4 of `SECURITY.md`) and wraps `ExecStart` in
`doppler run`. The application processes see secrets as ordinary
environment variables — no code change is required.

## Pre-flight checklist

- [ ] `doppler` binary present at `/usr/local/bin/doppler` (`doppler --version`)
- [ ] `/etc/digital-humans/doppler.env` exists, mode `0600`, owned by `root:root`, contains `DOPPLER_TOKEN=…`
- [ ] Doppler project `digital-humans` config `prod` is populated with at least: `DATABASE_URL`, `SECRET_KEY`, `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `CREDENTIALS_ENCRYPTION_KEY`
- [ ] Original units are backed up (`/etc/systemd/system/digital-humans-*.service.bak-YYYYMMDD`)

## Rollback

```bash
sudo cp /etc/systemd/system/digital-humans-backend.service.bak-YYYYMMDD \
        /etc/systemd/system/digital-humans-backend.service
sudo systemctl daemon-reload
sudo systemctl restart digital-humans-backend
```

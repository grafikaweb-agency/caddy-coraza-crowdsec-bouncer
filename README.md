# Caddy + Coraza + CrowdSec bouncer

Source repository for the shared Caddy image used by GrafikaWeb deployments. This repository builds and publishes the container image; deployment-specific Caddy routes and CrowdSec acquisition settings remain in each application deployment.

Published image:

```text
ghcr.io/grafikaweb-agency/caddy-coraza-crowdsec-bouncer:latest
```

The GitHub Actions workflow publishes on pushes to `main`, weekly, or manually. It uses the repository `GITHUB_TOKEN` with `packages: write`; the resulting GHCR package is associated with this repository rather than `fenuapro-erp`.

The image includes Caddy, the Coraza WAF module, and the HTTP CrowdSec bouncer module. CrowdSec's detection engine is deployed separately from this image.

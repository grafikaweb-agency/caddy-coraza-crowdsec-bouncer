# Caddy + Coraza + CrowdSec bouncer

Source repository for the shared Caddy image used by GrafikaWeb deployments. This repository builds and publishes the container image; deployment-specific Caddy routes and CrowdSec acquisition settings remain in each application deployment.

Published image:

```text
ghcr.io/grafikaweb-agency/caddy-coraza-crowdsec-bouncer:latest
```

The GitHub Actions workflow publishes on pushes to `main`, weekly, or manually. The `Containerfile` pins Caddy, Coraza, the CrowdSec bouncer, `xcaddy`, and its base image tags. Renovate proposes dependency and image updates as pull requests; it does not silently change the running image. The workflow uses the repository's `GITHUB_TOKEN` with `packages: write`; the resulting GHCR package is associated with this repository rather than `fenuapro-erp`.

The image includes Caddy, the Coraza WAF module, and the HTTP CrowdSec bouncer module. CrowdSec's detection engine is deployed separately from this image.

## Compatibility gate

Every pull request (including Renovate), merge queue candidate, main push and
scheduled build runs the `WAF compatibility` check. It builds the Containerfile,
checks the compiled modules and runs a real CrowdSec engine on a temporary
container network without publishing any ports. It checks benign GET/POST
requests, CRS XSS blocking for query strings and request bodies, IP banning,
isolation of an unbanned client and removal of the ban. A failed check prevents
publication; publication loads the exact tested image artifact.

Local execution:

```sh
podman build -t waf:ci -f Containerfile .
CONTAINER_ENGINE=podman python3 tests/integration.py
```

The test CrowdSec image is pinned in `tests/integration.py`. These integration
checks cover the combined proxy behavior, not every CRS rule or application
route. Configure branch protection for `main` with the required status check
`WAF compatibility`, require an up-to-date branch and apply it to administrators.
Renovate PRs must pass this check before merging. Do not rename the job without
also updating the required check in GitHub.

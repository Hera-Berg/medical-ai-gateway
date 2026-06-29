# Exposing the gateway with a Cloudflare Tunnel

This guide makes the Medical AI Gateway reachable on the public internet over a
**Cloudflare Tunnel** — an outbound-only connection from your machine to
Cloudflare's edge. No open inbound ports, no port forwarding, no public IP, and
you get Cloudflare's TLS + DDoS protection for free.

> **This project uses its own dedicated tunnel.** If you already run other
> tunnels on this machine (e.g. a filebrowser tunnel), they are untouched — a
> tunnel is just another `cloudflared` container with its own token. Nothing
> here interferes with existing tunnels.

## How it fits the stack

```
public internet
      │  (https://your-host.example.com)
      ▼
Cloudflare edge
      │  (outbound-only tunnel, encrypted)
      ▼
cloudflared container ──► nginx:80 ──► frontend / backend replicas
```

The `cloudflared` service is already defined in `docker-compose.yml` but sits
behind a Compose **profile** (`tunnel`), so it stays dormant during normal local
development and only starts when you explicitly ask for it. It is a
**remotely-managed** tunnel: all routing (which hostname maps to which internal
service) is configured in the Cloudflare dashboard, not in a local file. The
container only needs a **token**.

## Prerequisites

- A Cloudflare account (free tier is fine).
- A domain managed by Cloudflare (its nameservers pointed at Cloudflare). The
  tunnel attaches a public hostname under a domain you control.

## Step 1 — Create the tunnel in the dashboard

1. Go to the Cloudflare Zero Trust dashboard: **one.dash.cloudflare.com**
2. Navigate to **Networks → Tunnels**.
3. Click **Create a tunnel**, choose **Cloudflared** as the connector type.
4. Name it something specific so it doesn't get confused with other tunnels on
   this machine — e.g. `medical-ai-gateway` (not just `homelab`).
5. On the next screen Cloudflare shows an install command containing a token.
   **You only need the token** — the long `eyJ...` string. Copy it. (Skip
   running the install command; you'll run cloudflared via Docker instead.)

   > The token is shown once. If you lose it, regenerate it from the tunnel's
   > page (**Add a replica** reveals the install command + token again).

## Step 2 — Add the token to your environment

In the project root `.env` (copy from `.env.example` if you haven't), set:

```
CLOUDFLARE_TUNNEL_TOKEN=eyJ...your-token...
```

**Never commit `.env`** — it's gitignored. The token grants the ability to run
this tunnel; treat it like a password.

## Step 3 — Configure the public hostname (routing)

Still in the tunnel's dashboard page, go to the **Public Hostname** tab and add
a route:

| Field        | Value                          |
| ------------ | ------------------------------ |
| Subdomain    | e.g. `gateway`                 |
| Domain       | your Cloudflare-managed domain |
| Service type | `HTTP`                         |
| URL          | `http://nginx:80`            |

The critical part is the **service URL: `http://nginx:80`** (the dashboard requires the `http://` prefix). cloudflared and nginx share
the Compose default network, so cloudflared reaches nginx by its service name.
**Do not** point it at `localhost` — that would be the cloudflared container's
own localhost, not nginx.

This routes `https://gateway.yourdomain.com` → Cloudflare edge → tunnel →
`nginx:80`, which then serves the frontend and proxies `/api/` to the backend
replicas exactly as it does locally.

## Step 4 — Start the stack with the tunnel

Normal dev (no tunnel) is unchanged:

```bash
docker compose up -d --build
```

To bring the tunnel up too, activate the `tunnel` profile:

```bash
docker compose --profile tunnel up -d --build
```

Check the connector registered:

```bash
docker compose logs -f cloudflared
# look for: "Registered tunnel connection" / "Connection ... registered"
```

Then visit `https://gateway.yourdomain.com` — you should see the gateway, served
over Cloudflare's TLS, with no host ports exposed to the internet.

## Step 5 (recommended) — Lock it down with Cloudflare Access

This deployment has **no application-level authentication by design** (it's a
portfolio piece). The moment it's on the public internet, anyone with the URL
can use it — and every query (in real mode) costs GPU money. Put authentication
in front of it at the edge:

1. Zero Trust → **Access → Applications → Add an application** (Self-hosted).
2. Set the application domain to `gateway.yourdomain.com`.
3. Add a policy — e.g. allow only your own email, or emails ending in your
   domain, with one-time-PIN or SSO.

Now Cloudflare challenges every visitor before traffic reaches the tunnel. This
is the documented place to add auth given the app itself has none — and it's a
good thing to be able to point to: "no auth in the app by design, enforced at
the edge via Cloudflare Access."

## Turning it off

```bash
# stop just the tunnel, leave the app running locally
docker compose stop cloudflared

# or bring the whole stack down
docker compose --profile tunnel down
```

Stopping `cloudflared` immediately makes the public URL unreachable; the app
keeps running locally on `127.0.0.1:8090`.

## Notes & gotchas

- **Multiple tunnels on one machine:** each is its own container + token. This
  project's tunnel is independent of any other (e.g. filebrowser). They don't
  share state.
- **Local port still open:** `docker-compose.yml` publishes `127.0.0.1:8090:80`
  for local convenience. It's bound to loopback only, so it's not itself
  internet-exposed — but for a pure tunnel-only deployment you can remove that
  `ports:` line from the nginx service.
- **Costs:** with `MOCK_INFERENCE=1` (default) public visitors cost nothing.
  With a real RunPod endpoint, every query bills GPU time — another reason to
  enable Cloudflare Access before going live.
- **Token rotation:** rotate the token periodically from the dashboard; update
  `.env` and restart `cloudflared`.
```

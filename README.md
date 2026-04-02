<p align="center">
  <img src="https://user-images.githubusercontent.com/78877636/204297420-4b5373a8-4864-4710-a4a5-802ea4ec08d5.png#gh-dark-mode-only" width="500" height="300">
</p>
<p align="center">
  <img src="https://user-images.githubusercontent.com/78877636/204501041-a7cc2321-8991-4abb-a622-97f72f19051f.png#gh-light-mode-only" width="500" height="300">
</p>

# IntuneCD Monitor
This app is a frontend solution to the [IntuneCD python package](https://github.com/almenscorner/intunecd) that allows you to easily monitor tracked configurations, trends over time, differences between configurations across multiple tenants.

It's built using **FastAPI** and runs as a Docker stack (web, worker, beat) behind a **Caddy** reverse proxy with automatic TLS. The database backend is **PostgreSQL** (SQLite supported for local development).

The REST API is protected by an API key that is generated from the settings page, hashed with bcrypt, and stored in the database. UI access is gated by assignment to an app role on the Entra ID App Registration.

### Getting started

For help getting started, check out [Getting started](https://github.com/almenscorner/intunecd-monitor/wiki/deploy).

Have a look at the [Wiki](https://github.com/almenscorner/intunecd-monitor/wiki) to find documentation on how to use and configure the tool.

For release notes, have a look [here](https://github.com/almenscorner/intunecd-monitor/releases).


### Get help

There are a number of ways you can get help,
- Open an [issue](https://github.com/almenscorner/intunecd-monitor/issues) on this GitHub repo
- Start a [discussion](https://github.com/almenscorner/intunecd-monitor/discussions) on this GitHub repo
- Ask a question on [Discord](https://discord.gg/msems)
- Ask a question on [Slack](https://join.slack.com/t/intunecd/shared_invite/zt-1nf255xvo-POv60XoewYfY65TH9~tV_g)
- Check the [FAQ](https://github.com/almenscorner/intunecd-monitor/wiki/FAQ)

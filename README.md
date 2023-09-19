<p align="center">
  <img src="https://user-images.githubusercontent.com/78877636/204297420-4b5373a8-4864-4710-a4a5-802ea4ec08d5.png#gh-dark-mode-only" width="500" height="300">
</p>
<p align="center">
  <img src="https://user-images.githubusercontent.com/78877636/204501041-a7cc2321-8991-4abb-a622-97f72f19051f.png#gh-light-mode-only" width="500" height="300">
</p>

# IntuneCD Monitor
This app is a frontend solution to the [IntuneCD python package](https://github.com/almenscorner/intunecd) that allows you to easily monitor tracked configurations, trends over time, differences between configurations across multiple tenants.

It's built using Flask and running in a docker container behind an NGINX proxy. Since it is deployed to Azure App Service, SSL is handled by Microsoft and there's no need to build SSL support into the application.

The API to the application is protected by an API Key that is generated from the console and is hashed and stored in the Azure SQL database. Many of the actions in IntuneCD Monitor is protected by assignment to an admin role on the Entra ID app.

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

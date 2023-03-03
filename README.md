<p align="center">
  <img src="https://user-images.githubusercontent.com/78877636/204297420-4b5373a8-4864-4710-a4a5-802ea4ec08d5.png#gh-dark-mode-only" width="500" height="300">
</p>
<p align="center">
  <img src="https://user-images.githubusercontent.com/78877636/204501041-a7cc2321-8991-4abb-a622-97f72f19051f.png#gh-light-mode-only" width="500" height="300">
</p>

# IntuneCD Monitor
This app is a frontend solution to the [IntuneCD python package](https://github.com/almenscorner/intunecd) that allows you to easily monitor tracked configurations, trends over time, differences between configurations as well as your Azure DevOps pipeline status.

It's built using Flask and running in a docker container behind an NGINX proxy. Since it is deployed to Azure App Service, SSL is handled by Microsoft and there's no need to build SSL support into the application.

The API to the application is protected by an API Key that is generated from the console and is hashed and stored in the Azure SQL database. The Settings view is protected by role assignment on the Azure AD app, to access settings you must be an admin and to login to the app you must have at least one role assigned.

**Note:** While the IntuneCD package can run in either Azure DevOps pipelines or GitHub Actions, **only Azure DevOps pipelines** can be monitored using this application.

## What's new in 1.2.2
This update introduces exciting new features to the documentation section of the IntuneCD tool, along with several other improvements.

Firstly, the update removes the requirement for an admin role to access the change overview, making it more accessible to all users. Additionally, the change record count has been increased from 30 to 180 records, providing users with greater visibility into their system.

Furthermore, the update includes alerts for expiring API keys, ensuring that administrators are notified on the dashboard if an API key is expiring within 30 days.

Regarding the documentation section, a new page has been added that allows users to configure an Azure Storage account Container and Blob to pull documentation from in HTML format and display it in IntuneCD Monitor. To enable this feature, users must set the `DOCUMENTATION_ACTIVE` environment variable to true and provide the `AZURE_CONNECTION_STRING`, `AZURE_CONTAINER_NAME`, and `DOCUMENTATION_FILE_NAME` variables.

Overall, this update brings several exciting improvements and features to IntuneCD Monitor, making it more accessible and user-friendly for all users.

## What's new in 1.2.1
- It is now possible to search update and backup feed tables for specific configurations to be able to quickly check the config of interest instead of scrolling through all configs.

![Screenshot 2023-01-09 at 13 54 24](https://user-images.githubusercontent.com/78877636/211315009-760cedca-b3d2-42e0-bec5-0d624954bd3d.png)

# Table of contents

[Deploy this package](#deploy-this-package)
 - [Create Azure AD App Registration](#create-azure-ad-app-registration)
 - [Deploy to Azure](#deploy-to-azure)
 - [Configure pipelines](#configure-pipelines)
   - [Not using the update pipeline](#not-using-the-update-pipeline)

[Overview](#overview)
 - [Dashboard](#dashboard)
 - [Changes](#changes)
 - [Documentation](#documentation)
 - [Settings](#settings)
 - [Profile](#profile)

# Deploy this package
To deploy this package, all you have to do is click the button below. It will automatically deploy the following resources for you,
* Azure App Service Plan
* Azure SQL server and database
* Azure App Service

You only need to provide a few parameters to complete the deployment. Before continueing to deploy you need to create an Azure AD App Registration that will be used to authenticate to the site and provide the tokens needed to use Azure DevOps API.

## Create Azure AD App Registration
* Head over to [App Registrations](https://portal.azure.com/#view/Microsoft_AAD_IAM/ActiveDirectoryMenuBlade/~/RegisteredApps) in Azure AD and click New registration, provide a name and click register

![Screenshot 2022-09-26 at 14 34 18](https://user-images.githubusercontent.com/78877636/192277299-bc0b42d7-f20a-4dc6-a743-a69e48c658ab.png)

* Add the Azure DevOps API permission and grant admin consent

![Screenshot 2022-09-26 at 14 35 20](https://user-images.githubusercontent.com/78877636/192277492-08384e1e-ca57-4ebc-9503-465411199e9f.png)

* Click on App Roles and create a new role, the Value must be set to "intunecd_admin"

![Screenshot 2022-09-26 at 14 36 38](https://user-images.githubusercontent.com/78877636/192277729-15b4287b-f8bd-47cb-ab10-86f06598f9d2.png)

* Continue to create a secret for the application and save the secret value as well as the client ID, these will be needed in the next step.

## Deploy to Azure

Click the button below and fill out the fields that are not pre-populated, the name of the App Service will be the same as configured under **IntuneCD Instance Name**

[![Deploy to Azure](https://aka.ms/deploytoazurebutton)](https://portal.azure.com/#create/Microsoft.Template/uri/https%3A%2F%2Fraw.githubusercontent.com%2Falmenscorner%2Fintunecd-monitor%2Fmain%2Fdeploy_template.json)

<img width="666" alt="Screenshot 2022-08-31 at 14 35 33" src="https://user-images.githubusercontent.com/78877636/187683306-3229130e-2c22-4259-bc75-f4d7434815cf.png">

Once succussfully deployed, go back to the App Registration and add a new **Web** redirection URI, add the following URI: **https://{your_app_service_name}.azurewebsites.net/auth/signin-oidc**.

Navigate to [Azure AD Enterprise Applications](https://portal.azure.com/#view/Microsoft_AAD_IAM/StartboardApplicationsMenuBlade/~/AppAppsPreview/menuId~/null) and click on the IntuneCD Monitor app, add or edit an account you wish to be an admin in IntuneCD Monitor and assign the role created in prevoius steps.

That's it. After a successful deployment you will be able to navigate to **https://{your_app_service_name}.azurewebsites.net** and see this window,

![icdm_1](https://user-images.githubusercontent.com/78877636/204646110-6cef01cd-070c-45f4-8705-eff3e27c5533.png)

## Configure pipelines
To update IntuneCD Monitor with data from the pipelines, you will have to:
- generate a new API Key under settings in IntuneCD Monitor and configure this as an ENV variable named "API_KEY".
 - On the backup pipeline, configure the -f option like this `IntuneCD-startbackup -f https://{your_app_service_name}.azurewebsites.net` 
 - On the update pipeline configure the -f option like this `IntuneCD-startupdate -f https://{your_app_service_name}.azurewebsites.net`

### Not using the update pipeline

**NOTE**, as of version 1.3.0 of IntuneCD, you can just use `-r` when running `IntuneCD-startupdate` instead.

If you do not use IntuneCD to update configurations or if you do not have a DEV and PROD tenant, you can instead use [this script](./update_frontend.py) to update the frontend with changed values.

Using the script method you will instead back up the same environment at different intervals to separate folders, take the below example

```
|-Repo root
|---Backup one
|-----Configs
|---Backup two
|-----Configs
```

You could use two pipelines in this scenario that backs up the environment at different days, you could also inside the backup pipeline make sure you copy the current state to the "Backup two" folder before performing a new backup.

Then, create a pipeline that runs the above provided script or run it in the same pipeline if you go with the copy method, the flow of such a pipeline would be,

```
|-Copy current state to folder Backup two
|-Perform backup to folder Backup one
|-Commit changes
|-Run update_frontend.py
```

Required ENV variables are `BACKUP_PATH_ONE`, `BACKUP_PATH_TWO` and `API_KEY`. You also must update the frontend url on line 13.

An example Copy/Backup pipeline can be found [here](./example_pipeline.yml).

# Overview
## Dashboard
The dashboard is where you get a full picture of configurations tracked, differences found etc. From the dashboard you also get information on the pipelines used with IntuneCD, it is also possible to kick off a pipeline run.

![icdm_2](https://user-images.githubusercontent.com/78877636/204646551-4a2540ab-b69c-489d-a463-e335ff0f52cb.png)

## Changes
This page lets you review the last 30 records of changes made to configurations. When a configuration is clicked, details about the new and old values are revealed along with the date the change was reported.

![intunecd_changes](https://user-images.githubusercontent.com/78877636/210596785-54617b02-d43d-4ffc-b566-67e5058fc3c0.png)

## Documentation
If activated and configured, shows the documentation from HTML output stored on Azure Storage.

![icdm_documentation](https://user-images.githubusercontent.com/78877636/222262629-1e2bbc02-adb3-4947-835c-adb88726d13f.png)

## Settings
On the settings page you can find information on the ENV variables used for IntuneCD Monitor to work, not all variables are shown here only some essentials. From here you also generate the API Key that the IntuneCD package will use to update the frontend. The API Key is valid for 90 days after which you have to generate a new key. If a key is compromised it can also be deleted.

![icdm_3](https://user-images.githubusercontent.com/78877636/204646598-3c41ebca-0609-4adc-bb9a-b1e34f250da8.png)

## Profile
Displays some basic profile info and which role your account is assigned.

![icdm_4](https://user-images.githubusercontent.com/78877636/204646670-8dc81fdf-79b2-40b2-84af-c4b67650e6f2.png)

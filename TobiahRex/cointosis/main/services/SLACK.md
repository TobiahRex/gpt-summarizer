## Setup Instructions

1. Create a slack app inside the slack [app dashboard](https://api.slack.com/apps)
2. Inside the _Basic Information_ tab, select the _Add features and functionality_ sub section on the right-side panel.
    a. Within the badges section, select _Incoming Webhooks_ and add the integration.
    b. Within the _Permissions_ badge, you need to scroll down to the **Scopes** section, and add the following permissions. `channels:read`, `chat:write` and `incoming-webhook`.
3. Inside the _Basic Information_ tab, select the _Install your app_  and select the application from the menu, and then select the channel to implement the app.
4. Within the slack app, select the target channel you want to add the application to.  There will be several tabs, and one of them will be _integrations_, from which you should select the application by name you installed in the slack web dashboard.
5. This should be all the setup you require. To test the integration functionality, you can run the Slack Service `notify` method. Pay attention to any error messages for clues on where the setup went wrong in such a case.

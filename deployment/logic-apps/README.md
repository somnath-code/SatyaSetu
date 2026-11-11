# Connect approved claims notifications to Logic Apps

The [ARM template](workflow-template.json) creates an HTTP request trigger with the claims payload shape. It returns **501** until you configure a delivery action.

1. Deploy the template to your Azure resource group with [example parameters](parameters.example.json).
2. In the Logic Apps designer, add an email or Teams action for the claims reviewer. Use the notification ID, synthetic claim ID, rule codes, and policy version from the request.
3. Replace the placeholder response with **200** after the delivery action succeeds. Return a failure status when delivery fails.
4. Put the HTTPS callback URL in `CLAIMS_LOGIC_APP_CALLBACK_URL`. Use `claims notify` to preview approved messages. Run `claims notify --send` to send them to the configured workflow.

The dispatcher records uncertain results as `CHECK_DELIVERY`. Check Azure run history using the notification ID before resending. The template has no configured reviewer or connector credentials.

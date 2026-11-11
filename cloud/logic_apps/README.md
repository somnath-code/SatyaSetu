# Send ticket requests through Logic Apps

Configure an HTTP request workflow using the [Azure Logic Apps portal guide](https://learn.microsoft.com/en-us/azure/logic-apps/create-single-tenant-workflows-azure-portal?tabs=standard).

1. Add **When an HTTP request is received**. Use [request-schema.json](request-schema.json) for the request body and restrict access to the configured caller.
2. Add a **Switch** on the request body's `role` value. Add one branch per role: `BI_BA`, `ARCHITECT`, `DEVELOPER`, and `TESTER`.
3. In each branch add **Send an email (V2)** and select the team's configured reviewer address. Send the ticket ID, requirement ID and version, and finding code. If you have a tracker URL, add a link to the corresponding ticket. Keep the role-to-address mapping in Azure. A Teams action can replace email.
4. Add a **Response** with status **200** after the notification action succeeds. Return a non-success status for an unknown role or failed delivery. The Python dispatcher records a successful 200 and holds uncertain deliveries for review.
5. Set `LOGIC_APP_CALLBACK_URL` in your shell or secret manager. Keep the request URL out of source control.

~~~bash
brfss notify --out out/cdc
brfss notify --out out/cdc --send
~~~

The first command previews the payloads. The second sends them to your configured workflow. The recipient reviews the evidence and records a decision using `brfss decide`. Local decision logging uses a named reviewer and role for demonstration. A hosted deployment needs identity-backed reviewer authorization and its own ticket UI or tracker integration.

A 30-second timeout can occur after Azure accepts the request. Check Logic Apps run history against the ticket ID before attempting a resend. The dispatcher holds such requests in `CHECK_DELIVERY` and prevents concurrent duplicate sends from the same local ticket database.

# Walk through a synthetic claim

Start with [C002 in claims.csv](../data/sample/claims/claims.csv). It references E002, an IMAGE service for a BASIC-plan patient. The claim was submitted after the filing window and the amount is above the BASIC threshold.

~~~bash
claims demo
claims explain C002
claims search "late filing"
~~~

The [Gold pipeline](../src/healthcare/pipelines/gold.py) emits `COVERAGE`, `LATE_FILING`, and `HIGH_AMOUNT`. The explanation looks up those rule IDs in the [fictional policy](../data/sample/claims/policies/fictional-claims-policy.md) and returns the citations. C005 demonstrates the quarantine path because it references a missing encounter.

## Review a notification

~~~bash
claims draft C002
claims outbox
claims approve NOTICE_ID --reviewer "Demo reviewer" --note "Checked the cited fictional policy"
claims notify
~~~

Replace `NOTICE_ID` with the ID from the draft command. Repeating a draft for the same claim and rule set returns the same ID. `claims notify` previews approved payloads locally. Configure [Logic Apps](../deployment/logic-apps/README.md) before using `--send`.

## Check the evidence lookup

~~~bash
python evaluation/evaluate_agent.py
~~~

This evaluates the top policy section returned for four questions. The local evaluator measures retrieval. A hosted model's answer quality can be tested after you connect the [Agent Bricks tools](../agent/README.md).

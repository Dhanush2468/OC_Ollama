# Operations Console Investigation Flow

## Purpose
Investigate customer incidents in Operations Console where ED status is OK but ED service shows Major/Critical and condition is Subscription and Smart COM.

## Phase A: Initial Monitoring Extraction

1. Open Operations Console: https://console.share2act.io/
2. Sign in with Coprote ID via SSO.
3. Open Monitoring from the left panel.
4. Apply these filters:
   - ED Status: OK
   - ED Service Status: Major or Critical
   - ED Condition: Subscription and Smart COM
5. Click the Download icon on the right.
6. Open the downloaded file and use CSV format.
7. In the timestamp column, keep only customers in the last 24-hour window.
   - Example window: 16 June 12:30 to 17 June 12:29
8. Copy customer name(s).

## Phase B: Per-Customer Investigation Loop

Repeat steps 9-28 for each customer from Step 8.

9. Go back to Monitoring and search for the customer.
10. Open the customer record.
11. Check KOP/RK/ED Status. Continue only if status is OK.
12. Click Service Status (next to ED Status).
13. Hover error in DAS service status row.
14. Copy Adapter ID and capture datapoint names.
15. Expand Monitoring in the left panel.
16. Click DAS Validation.
17. Search for the Adapter ID.
18. Check Tag in error column. If numbers are red, click each Info (I) button.
19. Filter STATE column to error.

## LLM Validation Gate

At this point, LLM must compare datapoints under error state with the reference datapoint names attached in your document.

- If datapoints match reference list: continue to Step 20.
- If datapoints do not match: stop this customer and mark as non-target mismatch.

## Phase C: Connectivity Verification and Outcome

20. Go back to previous page.
21. Copy machine IP address for the Adapter ID.
22. Open SSM from the left panel.
23. Run command:
   - ping -c3 <IPADDRESS>
24. Click START COMMAND.
25. If ping is successful, continue.
26. Open Connectivity Check from the left panel.
27. If any red mark appears: classify as port issue and report to NOC team.
28. If all checks are green: classify as onsite issue and report to NOC.

## Outcome Labels (Recommended)

- Port Issue -> NOC escalation
- Onsite Issue -> NOC escalation
- Non-target Datapoint Mismatch -> close with mismatch note
- Status Not OK (Step 11 failed) -> skip customer
- Ping Failed -> host unreachable, escalate as connectivity failure

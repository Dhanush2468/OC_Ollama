# Latest Run Workflow Architecture

## Run Context
- Run ID: 2026-06-22-094134
- Timestamp: 2026-06-22T09:41:34
- Console URL: http://127.0.0.1:4173
- Report Source: output/findings/2026-06-22-094134.json

## End-to-End Architecture
The workflow is executed as a phased pipeline:
1. Phase A: Access + monitoring data extraction.
2. Phase B: Per-customer eligibility validation.
3. Phase C: Connectivity diagnosis and final NOC outcome.

Each customer moves through decision gates. A failed gate exits early with a defined status and outcome.

## Step-by-Step Flow

### Phase A: Access And Candidate Selection
1. Open Operations Console URL.
2. Execute SSO sign-in.
3. Open Monitoring module.
4. Open Account Monitoring and apply required filters.
5. Trigger CSV export from monitoring view.
6. Wait for download completion and detect latest CSV file.
7. Parse CSV and filter customers by configured time window (24h).
8. Build investigation queue up to max customers per run.

### Phase A Decision Gate
9. If strict 24h filter returns zero customers, log warning and use fallback queue from CSV without window filter.

### Phase B: Customer Investigation Loop
10. Start loop for each selected customer (with index and total counters).
11. Open Monitoring account view for the current customer.
12. Search customer name.
13. Open Readkit/Service status tabs.
14. Validate KOP/RK/ED status.
15. If status is not OK, mark customer as skipped with outcome: Skipped - Not Eligible (Status not OK), then continue to next customer.
16. If status is OK, capture adapter ID and detected datapoints from service details.
17. Open DAS Validation module.
18. Search adapter and open adapter details.
19. Filter DAS details by error state.
20. Extract error datapoints.
21. Compare against reference datapoint list (if configured).
22. If no match, mark customer as skipped with outcome: Skipped - Not Eligible (Datapoint mismatch), then continue to next customer.

### Phase C: Connectivity Diagnostics
23. Extract machine IP from available details.
24. Open SSM module.
25. Build ping command and execute remote command.
26. Evaluate ping output.
27. If ping fails, mark customer as failed with outcome: Host Unreachable - Ping Failed, then continue to next customer.
28. Open Connectivity Check and run CHECK ALL CONNECTIONS.
29. Evaluate connectivity output indicators.
30. If red/failed indicators are present, set outcome: NOC Report - Port Issue.
31. Otherwise, set outcome: NOC Report - Onsite Issue.
32. Capture final screenshot and persist customer result.

## Logging Architecture
The run now emits structured runtime logs:
1. PHASE logs: phase start, phase completion, and transition milestones.
2. STEP logs: explicit step execution markers.
3. WARN logs: fallback conditions such as zero strict-window customers.
4. ERROR logs: exceptions with customer context and step context.

The same progression is also stored in output JSON via:
1. phase_logs array
2. errors array

## Error Handling Model
1. Workflow-level operations use explicit checks for download and navigation failure.
2. Customer loop is wrapped with exception capture.
3. On customer exception, a failed customer result is written with outcome: Execution Error.
4. Execution continues to the next customer whenever possible.

## Latest Run Outcome Snapshot
1. Selected customers: 5 (using fallback because strict 24h filter returned zero).
2. Investigated customers: 5.
3. All 5 exited at status validation gate as skipped.
4. Captured errors list: empty.

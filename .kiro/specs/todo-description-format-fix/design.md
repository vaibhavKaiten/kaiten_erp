# TODO Description Format Fix - Bugfix Design

## Overview

This bugfix addresses inconsistent TODO task description formatting across execution workflows and other TODO types. Currently, TODO descriptions place the customer name first or use inconsistent formats (e.g., "tun mausi - TS-00123 - Initiate Technical Survey", "Create quotation for {customer_name}", "Collect Final Payment - {customer_first_name}{k_part} | {so_name}"), making it difficult for users to scan and filter tasks by action type. The fix will standardize the format to prioritize the task action over the customer name (e.g., "Initiate Technical Survey - tun mausi", "Create quotation - tun mausi", "Collect Final Payment - tun mausi"), improving task organization and user experience while preserving existing TODO formats for other workflow types.

The fix is minimal and targeted: update five string formatting statements in the codebase to reorder the description components. All other TODO creation logic (assignment, due dates, role filtering, duplicate prevention) remains unchanged.

## Glossary

- **Bug_Condition (C)**: The condition that triggers the bug - when a TODO is created for execution chain workflows (Technical Survey, Structure Mounting, Project Installation, Meter Installation, Meter Commissioning, Verification Handover) with the format "{customer_name} - {doc_name} - {action}", OR when "Create quotation" TODOs use "Create quotation for {customer_name}", OR when "Collect Final Payment" TODOs use "Collect Final Payment - {customer_first_name}{k_part} | {so_name}"
- **Property (P)**: The desired behavior - TODO descriptions should use the format "{action} - {customer_name}" for all affected workflows
- **Preservation**: All other TODO creation patterns (Follow-up, Create Sales Order, Create payment entry, Start DISCOM Process, Collect Structure Payment, Job File approval, Stock Manager transfers) must remain unchanged
- **Execution Chain Workflows**: The sequence of execution doctypes: Technical Survey → Structure Mounting → Project Installation → Meter Installation → Meter Commissioning → Verification Handover
- **Task Action**: The full task name that varies for each TODO (e.g., "Initiate Technical Survey", "Initiate Structure Mounting", "Initiate Project Installation", "Create quotation", "Collect Final Payment", etc.)
- **customer_first_name**: The Job File's first_name field or fallback to the Job File name, used in TODO descriptions

## Bug Details

### Bug Condition

The bug manifests when a TODO is created for any execution chain workflow, "Create quotation" tasks, or "Collect Final Payment" tasks. The description formatting functions place the customer name first or use inconsistent formats, making it difficult for users to scan task lists by action type since the distinguishing information (the action) appears at the end or is buried in the format.

**Formal Specification:**
```
FUNCTION isBugCondition(input)
  INPUT: input of type TodoCreationContext
  OUTPUT: boolean
  
  RETURN (
           input.workflow_type IN [
             'Initiate Technical Survey',
             'Initiate Structure Mounting', 
             'Initiate Project Installation',
             'Initiate Meter Installation',
             'Initiate Meter Commissioning',
             'Initiate Verification Handover'
           ]
           AND input.description_format == "{customer_name} - {doc_name} - {action}"
         )
         OR (
           input.workflow_type == 'Create quotation'
           AND input.description_format == "Create quotation for {customer_name}"
         )
         OR (
           input.workflow_type == 'Collect Final Payment'
           AND input.description_format == "Collect Final Payment - {customer_first_name}{k_part} | {so_name}"
         )
END FUNCTION
```

### Examples

**Current Defective Behavior:**

1. **Technical Survey TODO (from Job File Initiation)**:
   - Input: customer_first_name="tun mausi", technical_survey_name="TS-00123"
   - Current: "tun mausi - TS-00123 - Initiate Technical Survey"
   - Problem: Customer name appears first, making it hard to filter by "Initiate Technical Survey"

2. **Technical Survey TODO (from Quotation Acceptance)**:
   - Input: customer_name="John Doe", ts_name="TS-00456"
   - Current: "John Doe - TS-00456 - Initiate Technical Survey"
   - Problem: Same issue - action is buried at the end

3. **Execution Chain TODO (Structure Mounting → Project Installation)**:
   - Input: customer_first_name="Jane Smith", next_doc_name="PI-00789", next_doctype="Project Installation"
   - Current: "Jane Smith - PI-00789 - Initiate Project Installation"
   - Problem: Cannot easily scan for all "Initiate Project Installation" tasks

4. **Create Quotation TODO**:
   - Input: customer_name="Alice Johnson"
   - Current: "Create quotation for Alice Johnson"
   - Problem: Action is split by "for", making filtering inconsistent with other TODO formats

5. **Collect Final Payment TODO**:
   - Input: customer_first_name="Bob", k_number="K-123", so_name="SO-456"
   - Current: "Collect Final Payment - Bob (K-123) | SO-456"
   - Problem: Includes redundant information (k_number, so_name) that clutters the description

6. **Edge Case - Long Customer Name**:
   - Input: customer_first_name="Rajesh Kumar Sharma", next_doc_name="MI-01234", next_doctype="Meter Installation"
   - Current: "Rajesh Kumar Sharma - MI-01234 - Initiate Meter Installation"
   - Problem: Long customer name pushes action even further right in UI

**Expected Correct Behavior:**

1. "Initiate Technical Survey - tun mausi"
2. "Initiate Technical Survey - John Doe"
3. "Initiate Project Installation - Jane Smith"
4. "Create quotation - Alice Johnson"
5. "Collect Final Payment - Bob"
6. "Initiate Meter Installation - Rajesh Kumar Sharma"

## Expected Behavior

### Preservation Requirements

**Unchanged Behaviors:**

1. **Follow-up TODOs** (quotation_events.py, line ~138):
   - Format: "Follow-up: {customer} | {doc.name} | ₹{grand_total:,.0f}"
   - Must remain unchanged

2. **Create Sales Order TODOs** (quotation_events.py, line ~540):
   - Format: "Create Sales Order for {customer_name} | {doc.name} | ₹{grand_total:,.0f}"
   - Must remain unchanged

3. **Create Payment Entry TODOs** (JobFile_events.py, line ~267):
   - Format: "{customer_name} - {k_number}. Create payment entry - {amount}"
   - Must remain unchanged

4. **Start DISCOM Process TODOs**:
   - Format: "Start DISCOM Process - {customer_name}{k_part} | {doc.name}"
   - Must remain unchanged

5. **Collect Structure Payment TODOs**:
   - Existing format must remain unchanged

6. **Job File Approval TODOs** (JobFile_events.py, line ~711):
   - Format: "Job File {job_file.name} requires approval. Negotiated Amount (₹{amount}) is less than MRP (₹{mrp})."
   - Must remain unchanged

7. **Stock Manager Transfer TODOs**:
   - Existing format must remain unchanged

8. **TODO Assignment Logic**:
   - Role filtering (Vendor Head, Sales Manager, Execution Manager, Accounts Manager)
   - Duplicate prevention checks
   - Due date calculation
   - Status and priority settings
   - All must continue to work exactly as before

9. **TODO Closing Logic**:
   - Workflow state transitions that close TODOs
   - Description pattern matching for closing TODOs (e.g., "like '%Initiate Technical Survey%'", "like 'Collect Final Payment%'")
   - Must continue to work with new description format

**Scope:**

All TODO creation that does NOT involve execution chain workflows, "Create quotation" tasks, or "Collect Final Payment" tasks should be completely unaffected by this fix. This includes:
- Quotation follow-up TODOs
- Sales Order creation TODOs
- Payment entry TODOs
- DISCOM process TODOs
- Structure payment TODOs
- Job File approval TODOs
- Stock Manager transfer TODOs
- All TODO querying and filtering operations

## Hypothesized Root Cause

Based on the bug description and code analysis, the root cause is straightforward:

1. **Incorrect String Formatting Order**: The f-string templates in five locations use inconsistent patterns instead of the standardized `f"{action} - {customer_name}"` format:
   - `JobFile_events.py` line 751: Technical Survey TODO on Job File Initiation - uses `f"{customer_name} - {doc_name} - {action}"`
   - `quotation_events.py` line 458: Technical Survey TODO on Quotation Acceptance - uses `f"{customer_name} - {doc_name} - {action}"`
   - `execution_chain_todo.py` line 161: All execution chain TODOs - uses `f"{customer_name} - {doc_name} - {action}"`
   - `JobFile_events.py` line 540: Create quotation TODO - uses `"Create quotation for {customer_name}"`
   - `execution_chain_todo.py` line 280: Collect Final Payment TODO - uses `f"Collect Final Payment - {customer_first_name}{k_part} | {so_name}"`

2. **No Architectural Issue**: This is purely a formatting bug. The TODO creation logic, assignment, duplicate prevention, and workflow integration all work correctly. Only the description strings need reordering and simplification.

3. **Historical Context**: The original formats may have been chosen to include additional context (document names, k_numbers, SO names), but user feedback indicates that a simpler, action-first format is more valuable for task management and filtering.

## Correctness Properties

Property 1: Bug Condition - Standardized TODO Format

_For any_ TODO creation where the workflow type is an execution chain action (Initiate Technical Survey, Initiate Structure Mounting, Initiate Project Installation, Initiate Meter Installation, Initiate Meter Commissioning, Initiate Verification Handover), "Create quotation", or "Collect Final Payment", the fixed code SHALL create a description in the format "{Task Action} - {customer_name}", placing the task action first to enable easy scanning and filtering by action type.

**Validates: Requirements 2.1, 2.2, 2.3, 2.4, 2.5**

Property 2: Preservation - Non-Affected TODO Formats

_For any_ TODO creation that is NOT an execution chain workflow, "Create quotation", or "Collect Final Payment" (Follow-up, Create Sales Order, Create payment entry, Start DISCOM Process, Collect Structure Payment, Job File approval, Stock Manager transfers), the fixed code SHALL produce exactly the same description format as the original code, preserving all existing TODO patterns and user expectations for non-affected workflows.

**Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8**

## Fix Implementation

### Changes Required

The fix requires updating five string formatting statements to reorder description components and remove redundant information. No logic changes are needed.

**File 1**: `kaiten_erp/kaiten_erp/doc_events/JobFile_events.py`

**Function**: `assign_vendor_head_todos` (around line 751)

**Specific Changes**:
1. **Current Line 751**:
   ```python
   description = f"{customer_first_name} - {technical_survey_name} - Initiate Technical Survey"
   ```
   
2. **Fixed Line**:
   ```python
   description = f"Initiate Technical Survey - {customer_first_name}"
   ```

3. **Rationale**: Remove the document name (technical_survey_name) from the description as it's redundant (already stored in reference_name field) and reorder to put action first.

---

**File 2**: `kaiten_erp/kaiten_erp/doc_events/quotation_events.py`

**Function**: `_create_vendor_head_initiate_ts_todo` (around line 458)

**Specific Changes**:
1. **Current Line 458**:
   ```python
   description = f"{customer_name} - {ts_name} - Initiate Technical Survey"
   ```
   
2. **Fixed Line**:
   ```python
   description = f"Initiate Technical Survey - {customer_name}"
   ```

3. **Rationale**: Remove the document name (ts_name) and reorder to put action first, matching the pattern from File 1.

---

**File 3**: `kaiten_erp/kaiten_erp/api/execution_chain_todo.py`

**Function**: `_create_vendor_head_todos` (around line 161)

**Specific Changes**:
1. **Current Line 161**:
   ```python
   description = f"{customer_first_name} - {next_doc_name} - Initiate {next_doctype}"
   ```
   
2. **Fixed Line**:
   ```python
   description = f"Initiate {next_doctype} - {customer_first_name}"
   ```

3. **Rationale**: Remove the document name (next_doc_name) and reorder to put action first. This single change fixes all execution chain TODOs (Structure Mounting, Project Installation, Meter Installation, Meter Commissioning, Verification Handover).

---

**File 4**: `kaiten_erp/kaiten_erp/doc_events/JobFile_events.py`

**Function**: `assign_sales_manager_todos` (around line 540)

**Specific Changes**:
1. **Current Line 540**:
   ```python
   description = _("Create quotation for {0}").format(customer_name)
   ```
   
2. **Fixed Line**:
   ```python
   description = _("Create quotation - {0}").format(customer_name)
   ```

3. **Rationale**: Change "for" to "-" to match the standardized format pattern, making it consistent with other TODO descriptions and easier to scan.

---

**File 5**: `kaiten_erp/kaiten_erp/api/execution_chain_todo.py`

**Function**: `_sf_intercept_mc_approved` (around line 280)

**Specific Changes**:
1. **Current Lines 280-283**:
   ```python
   description = (
       f"Collect Final Payment"
       f" - {customer_first_name}{k_part}"
       f" | {so_name}"
   )
   ```
   
2. **Fixed Line**:
   ```python
   description = f"Collect Final Payment - {customer_first_name}"
   ```

3. **Rationale**: Remove redundant information (k_number in k_part, so_name) that clutters the description. The reference_name field already stores the Sales Order name, and the k_number can be accessed through the Job File if needed. Simplify to match the standardized format.

---

**Impact Analysis**:

1. **TODO Closing Logic**: The code uses pattern matching like `"description": ["like", "%Initiate Technical Survey%"]` and `"description": ["like", "Collect Final Payment%"]` to close TODOs. This will continue to work because the action text is still present at the beginning of the description.

2. **Duplicate Prevention**: The duplicate checks use reference_type, reference_name, allocated_to, and role - not the description field. No impact.

3. **UI Display**: TODOs will now be easier to scan and filter by action type in the UI.

4. **Existing Open TODOs**: Already-created TODOs with the old format will remain unchanged. Only new TODOs will use the new format. This is acceptable as the old TODOs will be closed through normal workflow progression.

## Testing Strategy

### Validation Approach

The testing strategy follows a two-phase approach: first, surface counterexamples that demonstrate the bug on unfixed code by inspecting TODO descriptions, then verify the fix produces correct descriptions and preserves all other TODO creation patterns.

### Exploratory Bug Condition Checking

**Goal**: Surface counterexamples that demonstrate the bug BEFORE implementing the fix. Confirm the root cause analysis by observing the incorrect description format in created TODOs.

**Test Plan**: Create test scenarios that trigger TODO creation for each affected workflow type. Inspect the created TODO descriptions to verify they use the incorrect formats. Run these tests on the UNFIXED code to observe the defective behavior.

**Test Cases**:

1. **Job File Initiation - Technical Survey TODO**:
   - Setup: Create a Job File with first_name="Test Customer", transition to "Job File Initiated" state
   - Observe: TODO description for Vendor Head users
   - Expected Counterexample: "Test Customer - TS-XXXXX - Initiate Technical Survey" (will fail - customer name is first)

2. **Quotation Acceptance - Technical Survey TODO**:
   - Setup: Create a Quotation with customer_name="Jane Doe", set custom_customer_acceptance="Yes"
   - Observe: TODO description for Vendor Head users
   - Expected Counterexample: "Jane Doe - TS-XXXXX - Initiate Technical Survey" (will fail - customer name is first)

3. **Structure Mounting Approved - Project Installation TODO**:
   - Setup: Create Structure Mounting document, transition workflow_state to "Approved"
   - Observe: TODO description for Vendor Head users
   - Expected Counterexample: "Customer Name - PI-XXXXX - Initiate Project Installation" (will fail - customer name is first)

4. **Project Installation Approved - Meter Installation TODO**:
   - Setup: Create Project Installation document, transition workflow_state to "Approved"
   - Observe: TODO description for Vendor Head users
   - Expected Counterexample: "Customer Name - MI-XXXXX - Initiate Meter Installation" (will fail - customer name is first)

5. **Meter Installation Approved - Meter Commissioning TODO**:
   - Setup: Create Meter Installation document, transition workflow_state to "Approved"
   - Observe: TODO description for Vendor Head users
   - Expected Counterexample: "Customer Name - MC-XXXXX - Initiate Meter Commissioning" (will fail - customer name is first)

6. **Meter Commissioning Approved - Verification Handover TODO**:
   - Setup: Create Meter Commissioning document, transition workflow_state to "Approved"
   - Observe: TODO description for Vendor Head users
   - Expected Counterexample: "Customer Name - VH-XXXXX - Initiate Verification Handover" (will fail - customer name is first)

7. **Job File Initiated - Create Quotation TODO**:
   - Setup: Create a Job File with customer_name="Alice Johnson", transition to "Job File Initiated" state
   - Observe: TODO description for Sales Manager users
   - Expected Counterexample: "Create quotation for Alice Johnson" (will fail - uses "for" instead of "-")

8. **Meter Commissioning Approved (Self Finance) - Collect Final Payment TODO**:
   - Setup: Create Meter Commissioning for Self Finance Sales Order, transition to "Approved"
   - Observe: TODO description for Sales Manager users
   - Expected Counterexample: "Collect Final Payment - Bob (K-123) | SO-456" (will fail - includes redundant k_number and so_name)

**Expected Counterexamples**:
- Execution chain TODOs will have customer name first, making action scanning difficult
- Document names appear in the middle, adding redundant information (already in reference_name)
- Actions appear last, requiring users to read the entire description to identify the task type
- "Create quotation" uses "for" instead of "-", breaking format consistency
- "Collect Final Payment" includes redundant k_number and so_name, cluttering the description

### Fix Checking

**Goal**: Verify that for all inputs where the bug condition holds (affected TODO creation), the fixed function produces the expected description format.

**Pseudocode:**
```
FOR ALL input WHERE isBugCondition(input) DO
  result := createTodoDescription_fixed(input)
  ASSERT result.format == "{action} - {customer_name}"
  ASSERT result.starts_with(input.action)
  ASSERT result.ends_with(input.customer_name)
  ASSERT NOT result.contains(input.doc_name)
  ASSERT NOT result.contains(input.k_number)
  ASSERT NOT result.contains(input.so_name)
END FOR
```

**Test Cases**:

1. **Technical Survey TODO (Job File)**:
   - Input: customer_first_name="Alice", technical_survey_name="TS-001"
   - Expected: "Initiate Technical Survey - Alice"
   - Verify: Action first, customer last, no doc name

2. **Technical Survey TODO (Quotation)**:
   - Input: customer_name="Bob", ts_name="TS-002"
   - Expected: "Initiate Technical Survey - Bob"
   - Verify: Action first, customer last, no doc name

3. **Structure Mounting → Project Installation**:
   - Input: customer_first_name="Charlie", next_doc_name="PI-003", next_doctype="Project Installation"
   - Expected: "Initiate Project Installation - Charlie"
   - Verify: Action first, customer last, no doc name

4. **Project Installation → Meter Installation**:
   - Input: customer_first_name="Diana", next_doc_name="MI-004", next_doctype="Meter Installation"
   - Expected: "Initiate Meter Installation - Diana"
   - Verify: Action first, customer last, no doc name

5. **Meter Installation → Meter Commissioning**:
   - Input: customer_first_name="Eve", next_doc_name="MC-005", next_doctype="Meter Commissioning"
   - Expected: "Initiate Meter Commissioning - Eve"
   - Verify: Action first, customer last, no doc name

6. **Meter Commissioning → Verification Handover**:
   - Input: customer_first_name="Frank", next_doc_name="VH-006", next_doctype="Verification Handover"
   - Expected: "Initiate Verification Handover - Frank"
   - Verify: Action first, customer last, no doc name

7. **Create Quotation TODO**:
   - Input: customer_name="Grace"
   - Expected: "Create quotation - Grace"
   - Verify: Uses "-" instead of "for", action first, customer last

8. **Collect Final Payment TODO**:
   - Input: customer_first_name="Henry", k_number="K-123", so_name="SO-456"
   - Expected: "Collect Final Payment - Henry"
   - Verify: Action first, customer last, no k_number, no so_name

### Preservation Checking

**Goal**: Verify that for all inputs where the bug condition does NOT hold (non-affected TODO creation), the fixed function produces the same result as the original function.

**Pseudocode:**
```
FOR ALL input WHERE NOT isBugCondition(input) DO
  ASSERT createTodoDescription_original(input) = createTodoDescription_fixed(input)
END FOR
```

**Testing Approach**: Property-based testing is recommended for preservation checking because:
- It generates many test cases automatically across the input domain
- It catches edge cases that manual unit tests might miss
- It provides strong guarantees that behavior is unchanged for all non-affected TODOs
- The TODO creation codebase has many different patterns that need verification

**Test Plan**: Observe behavior on UNFIXED code first for all non-affected TODO types, then write property-based tests capturing that exact behavior to ensure the fix doesn't introduce regressions.

**Test Cases**:

1. **Follow-up TODO Preservation**:
   - Observe: Create Quotation, set custom_next_followup_date, verify description format
   - Expected: "Follow-up: {customer} | {doc.name} | ₹{grand_total:,.0f}"
   - Test: Verify format unchanged after fix

2. **Create Sales Order TODO Preservation**:
   - Observe: Create Quotation with custom_customer_acceptance="Yes" and custom_technical_survey set
   - Expected: "Create Sales Order for {customer_name} | {doc.name} | ₹{grand_total:,.0f}"
   - Test: Verify format unchanged after fix

3. **Create Payment Entry TODO Preservation**:
   - Observe: Create Job File, set token_amount_recieved
   - Expected: "{customer_name} - {k_number}. Create payment entry - {amount}"
   - Test: Verify format unchanged after fix

4. **Start DISCOM Process TODO Preservation**:
   - Observe: Create relevant document, trigger DISCOM process TODO
   - Expected: "Start DISCOM Process - {customer_name}{k_part} | {doc.name}"
   - Test: Verify format unchanged after fix

5. **Collect Structure Payment TODO Preservation**:
   - Observe: Create relevant document, trigger structure payment TODO
   - Expected: Existing format unchanged
   - Test: Verify format unchanged after fix

6. **Job File Approval TODO Preservation**:
   - Observe: Create Job File, transition to "Approval Pending"
   - Expected: "Job File {job_file.name} requires approval. Negotiated Amount (₹{amount}) is less than MRP (₹{mrp})."
   - Test: Verify format unchanged after fix

7. **TODO Closing Pattern Matching**:
   - Observe: Close TODOs using pattern matching like `["like", "%Initiate Technical Survey%"]` and `["like", "Collect Final Payment%"]`
   - Expected: Pattern matching continues to work with new description format
   - Test: Verify TODOs are closed correctly when workflow states change

8. **Duplicate Prevention Logic**:
   - Observe: Attempt to create duplicate TODOs with same reference_type, reference_name, allocated_to, role
   - Expected: Duplicate prevention works regardless of description format
   - Test: Verify no duplicate TODOs are created after fix

### Unit Tests

- Test each of the five fixed functions in isolation with mock data
- Verify description format matches "{action} - {customer_name}" pattern
- Test edge cases: empty customer names, special characters in names, very long names
- Verify all other TODO fields (reference_type, reference_name, allocated_to, role, priority, status, date) are set correctly
- Test that document name, k_number, and so_name are NOT included in the description for affected TODOs
- Test that "Create quotation" uses "-" instead of "for"
- Test that "Collect Final Payment" excludes k_number and so_name

### Property-Based Tests

- Generate random customer names (various lengths, special characters, Unicode) and verify description format
- Generate random execution chain workflows and verify all produce correct format
- Generate random "Create quotation" and "Collect Final Payment" scenarios and verify correct format
- Generate random non-affected TODO scenarios and verify preservation
- Test that pattern matching for TODO closing works across many generated descriptions
- Verify duplicate prevention works across many generated TODO creation attempts

### Integration Tests

- Test full Job File initiation flow: verify Technical Survey TODO and Create Quotation TODO have correct formats
- Test full Quotation acceptance flow: verify Technical Survey TODO has correct format
- Test full execution chain: Structure Mounting → Project Installation → Meter Installation → Meter Commissioning → Verification Handover, verify all TODOs have correct format
- Test Self Finance Meter Commissioning approval: verify Collect Final Payment TODO has correct format
- Test workflow state transitions that close TODOs: verify pattern matching works with new format
- Test UI filtering and searching: verify users can easily filter by action type with new format
- Test that existing open TODOs with old format coexist with new TODOs without issues

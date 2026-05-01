# Bugfix Requirements Document

## Introduction

This bugfix addresses an inconsistent TODO task description format across the system. Currently, when TODO tasks are created for various execution workflows (Technical Survey, Structure Mounting, Project Installation, Meter Installation, Meter Commissioning, Verification Handover), the description format is inconsistent with the expected standard format.

The bug affects user experience and task organization, as users expect a standardized format that prioritizes the task action over the customer name for better task scanning and filtering.

## Bug Analysis

### Current Behavior (Defect)

1.1 WHEN a TODO is created for "Initiate Technical Survey" with customer "tun mausi" THEN the system creates a description in the format "{customer_name} - {doc_name} - Initiate Technical Survey" (e.g., "tun mausi - TS-00123 - Initiate Technical Survey")

1.2 WHEN a TODO is created for any execution chain workflow (Structure Mounting, Project Installation, Meter Installation, Meter Commissioning, Verification Handover) THEN the system creates a description in the format "{customer_name} - {doc_name} - Initiate {doctype}"

1.3 WHEN a TODO is created for "Initiate Verification Handover" THEN the system creates a description in the format "{customer_name} - {doc_name} - Initiate Verification Handover"

1.4 WHEN a TODO is created for "Create quotation" tasks THEN the system creates a description in the format "Create quotation for {customer_name}"

1.5 WHEN a TODO is created for "Collect Final Payment" tasks THEN the system creates a description in the format "Collect Final Payment - {customer_first_name}{k_part} | {so_name}"

### Expected Behavior (Correct)

2.1 WHEN a TODO is created for "Initiate Technical Survey" with customer "tun mausi" THEN the system SHALL create a description in the format "Initiate Technical Survey - {customer_name}" (e.g., "Initiate Technical Survey - tun mausi")

2.2 WHEN a TODO is created for any execution chain workflow (Structure Mounting, Project Installation, Meter Installation, Meter Commissioning, Verification Handover) THEN the system SHALL create a description in the format "Initiate {doctype} - {customer_name}"

2.3 WHEN a TODO is created for "Initiate Verification Handover" THEN the system SHALL create a description in the format "Initiate Verification Handover - {customer_name}"

2.4 WHEN a TODO is created for "Create quotation" tasks THEN the system SHALL create a description in the format "Create quotation - {customer_name}"

2.5 WHEN a TODO is created for "Collect Final Payment" tasks THEN the system SHALL create a description in the format "Collect Final Payment - {customer_name}"

### Unchanged Behavior (Regression Prevention)

3.1 WHEN a TODO is created for "Follow-up" tasks on Quotations THEN the system SHALL CONTINUE TO use the format "Follow-up: {customer} | {doc.name} | ₹{grand_total:,.0f}"

3.2 WHEN a TODO is created for "Create Sales Order" tasks THEN the system SHALL CONTINUE TO use the format "Create Sales Order for {customer_name} | {doc.name} | ₹{grand_total:,.0f}"

3.3 WHEN a TODO is created for "Create payment entry" tasks THEN the system SHALL CONTINUE TO use the format "{customer_name} - {k_number}. Create payment entry - {amount}"

3.4 WHEN a TODO is created for "Start DISCOM Process" tasks THEN the system SHALL CONTINUE TO use the format "Start DISCOM Process - {customer_name}{k_part} | {doc.name}"

3.5 WHEN a TODO is created for "Collect Structure Payment" tasks THEN the system SHALL CONTINUE TO use their existing format

3.6 WHEN a TODO is created for Job File approval by Execution Managers THEN the system SHALL CONTINUE TO use the format "Job File {job_file.name} requires approval. Negotiated Amount (₹{amount}) is less than MRP (₹{mrp})."

3.7 WHEN a TODO is created for Stock Manager transfer tasks THEN the system SHALL CONTINUE TO use their existing format

3.8 WHEN TODOs are closed, filtered, or queried by description patterns THEN the system SHALL CONTINUE TO function correctly with the new description format

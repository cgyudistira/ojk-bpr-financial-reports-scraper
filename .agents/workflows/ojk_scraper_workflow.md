---
description: OJK BPR Scraper UI Automation Workflow
---

# OJK BPR Scraper Automation Workflow - Ext.NET Handling

This OJK BPR Konvensional scraper interacts with an ASP.NET application rendered via Ext.NET (An ExtJS wrapper). There are specific characteristics in the UI that cause ordinary Selenium interaction tools to fail their normal operations:

## 1. Cascading Dropdown Interaction (ComboBox)
Standard HTML `<select>` dropdowns are not used. OJK utilizes `Ext.form.ComboBox`. 
- If the ComboBox value is mutated utilizing only `Ext.getCmp('Id').setValue('xxx')`, the required server-side postback (`DirectEvent`) will never trigger, resulting directly in the child dropdowns (e.g., City selection after Province selection) failing to load their specific data (Breaking the Cascade Loading loop).
- **Proper Solution**: Utilize the UI Native API `cmp.expand()` to visually open the dropdown, pause to ensure the internal component list (*picker*) is rendered, and then explicitly simulate a DOM `click()` to the child dropdown data element via `picker.getNode(record).click()`. This natively fires the required DOM event bound to the hidden ASP.NET trigger mechanism.

## 2. Specialized "BankCode" Dropdown Field
The dropdown used specifically for Bank Names (`Ext.getCmp('BankCode')`) diverges heavily from the previously mentioned logic. The UI implements a hierarchical tree structure (`TreeStore`) marking the class as an `Ext.net.DropDownField`.
- This dropdown is explicitly isolated from the generic cascading interaction triggers.
- **Proper Solution**: We can invoke direct JavaScript manipulation using `cmp.setValue('bank_code')` directly on `BankCode`. Under the hood, this bypasses the visual limitations and forcibly populates the internal *ReportTree* elements instantly.

## 3. Invoking Report Checkboxes (ReportTree Node Selection)
The targeted financial reports are modeled as Node objects inside the hierarchical `ReportTree`.
- Native Selenium clicks targeting checkboxes fail frequently if the elements render off-screen or trigger unforeseen layout reflows in the table node hierarchy.
- **Proper Solution**: Employ ExtJS iterative APIs via `t.getRootNode().cascadeBy(function(node) { ... })` to transverse elements. Override the boolean values manually via `node.set('checked', true)` and synthesize the expected handler using `t.fireEvent('checkchange', node, true)`.

## 4. Ext.NET Exploitation via Hidden Form Variables (`ReportTree_CheckNodes`)
This represents the greatest blockage interacting with the application (A systematic flaw in OJK / Ext.NET). When the user attempts to invoke the "Show" Action Button using `Ext.getCmp('ShowReportButton').getEl().dom.click()`, the recorded checkboxes values inside the `ReportTree` *MIGHT* be dispatched as intentionally empty arrays by the server because dynamically altering states mathematically via `fireEvent` failed to bind to the hidden POST variables.
- Ext.NET structurally stores "Checked Document Lists" globally inside an HTML hidden input named explicitly as `ReportTree_CheckNodes` allowing the variable string to intercept the HTTP POST stream.
- **Proper Solution (Critical Fix)**: Before clicking the Final Display Button, the scraper MUST manually intercept and override the DOM object value: `document.getElementsByName('ReportTree_CheckNodes')[0].value = checkedIds.join(',');`. This represents the primary vulnerability why ExtJS requests historically rendered empty payload values.

## 5. Execution Invocation Button (`ShowReportButton`)
The `ExtJS` button halts the dispatch of POST requests if standard `.click()` interaction patterns are leveraged via Selenium or generic Ext triggers like `fireEvent('click')`.
- **Proper Solution**: Extensively, only the raw `btn.getEl().dom.click()` node registers and dispatches the native listening requirement associated with DOM `MouseEvent`, subsequently resulting in the Javascript sandbox correctly dispatching the targeted external requests against the ASP.NET architecture.

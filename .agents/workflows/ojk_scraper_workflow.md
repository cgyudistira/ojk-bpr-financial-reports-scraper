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

## 4. Ext.NET Form Serialization: `ReportTree_CheckNodes` Hidden Field
This represents the greatest blockage interacting with the application. When the "Tampilkan" button is clicked, the server deserializes `ReportTree_CheckNodes` into `Ext.Net.SubmittedNode` objects. Using `fireEvent('checkchange')` or manually setting the field to a comma-separated string like `"BPK-901-000001,BPK-901-000002"` causes:
- `"Could not cast or convert from System.String to Ext.Net.SubmittedNode"` (JSON.stringify)
- `"Unexpected character encountered while parsing value: B"` (comma-joined string)

**Proper Solution**: Use the **native ExtJS view method** `t.getView().onCheckChange(node, true)` instead of `fireEvent`. This method internally serializes each node into the correct JSON format:
```json
[{"nodeID":"BPK-901-000001","clientID":"BPK-901-000001","text":"...","path":"/root/BPK-901-000001","attributes":{"checked":true,"qshowDelay":0}}, ...]
```

## 5. BankCode Value Format (Critical)
The `BankCode` input value must include both the numeric code AND the bank name, separated by a hyphen. Example: `600083-PT Bank Perekonomian Rakyat Duta Bali`. The server's `ShowReportButton_DirectClick` handler performs `String.Substring` to split the code from the name at the hyphen position. Sending only the numeric code (`600083`) causes:
- `"Length cannot be less than zero. Parameter name: length"` (because `IndexOf('-')` returns -1)

## 6. ProvinceCode/CityCode Input Values
Ext.NET ComboBox does not have `hiddenName` configured, so the visible `<input type="text">` element submits the **display text** (e.g., "Provinsi Bali") instead of the value code ("DATI01126"). Before clicking the Tampilkan button, the scraper must override the input element values:
```javascript
var prov = Ext.getCmp('ProvinceCode');
if (prov) prov.inputEl.dom.value = prov.getValue(); // Sets "DATI01126"
```

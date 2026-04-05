---
description: OJK BPR Scraper UI Automation Workflow
---

# Alur Kerja Scraper OJK BPR - Penanganan Ext.NET

Scraper OJK BPR Konvensional ini berhadapan dengan aplikasi ASP.NET yang dirender via Ext.NET (ExtJS wrapper). Ada beberapa karakteristik khusus pada UI yang menyebabkan alat interaksi Selenium biasa gagal beroperasi normal:

## 1. Interaksi Dropdown (Cascading ComboBox)
Dropdown standar HTML `<select>` tidak digunakan. OJK menggunakan Ext.form.ComboBox. 
- Jika nilai ComboBox hanya diubah menggunakan `Ext.getCmp('Id').setValue('xxx')`, event server (postback/DirectEvent) tidak akan terpicu, dan dropdown turunan (seperti Kabupaten jika Provinsi dipilih) tidak akan memuat data (Cascade Loading putus).
- **Solusi Tepat**: Gunakan fungsi API UI `cmp.expand()` untuk membuka dropdown, tunggu list komponen (*picker*) ter-render, kemudian simulasikan `click()` ke elemen DOM dropdown menggunakan `picker.getNode(record).click()`. Ini memicu event DOM native yang ditangkap oleh ASP.NET di belakang layar.

## 2. Dropdown Khusus "BankCode"
Dropdown untuk nama bank (`Ext.getCmp('BankCode')`) berbeda. UI dropdown merender hierarki (TreeStore) sehingga ini adalah `Ext.net.DropDownField`.
- Dropdown ini diabaikan dari trigger ASP.NET cascading reguler.
- **Solusi Tepat**: Kita dapat secara langsung menggunakan JavaScript `cmp.setValue('kode')` pada `BankCode`. Yang terjadi di latar belakang adalah *ReportTree* langsung dimuat isinya.

## 3. Centang Pohon Laporan (ReportTree Checkboxes)
Laporan yang diinginkan digambarkan dalam bentuk objek Node di pohon hierarki *ReportTree*.
- *Selenium Native Click* pada checkbox terkadang bermasalah saat elemen berada di luar layar atau saat memicu reflow.
- **Solusi Tepat**: Gunakan API ExtJS untuk melakukan iterasi node (`t.getRootNode().cascadeBy(function(node) { ... })`), ubah state `node.set('checked', true)` dan bakar *event handler* melalui `t.fireEvent('checkchange', node, true)`.

## 4. Kelemahan Ext.NET pada Form Hidden Variables (ReportTree_CheckNodes)
Ini adalah masalah terberat (BUG SISTEM OJK / Ext.NET). Saat klik tombol "Tampilkan" dengan `Ext.getCmp('ShowReportButton').getEl().dom.click()`, nilai centang di `ReportTree` BISA SAJA kosong pada server jika kita mengubah visual state checkbox secara dinamis lewat `fireEvent`.
- Ext.NET menyimpan "Daftar Laporan Tercentang" ke dalam *hidden input HTML* bernama `ReportTree_CheckNodes` yang akan menjadi bagian dari form-data di HTTP POST.
- **Solusi Tepat (Critical Hack)**: Sebelum mengklik tombol Tampilkan, scraper WAJIB secara manual mengisi *DOM Element*: `document.getElementsByName('ReportTree_CheckNodes')[0].value = checkedIds.join(',');`. Ini adalah kunci utama mengapa laporan dapat tertampil.

## 5. Tombol eksekusi Tampilkan (ShowReportButton)
Tombol extjs tidak mengirim POST request jika di *click* menggunakan Selenium `.click()` atau jika `fireEvent('click')` dilakukan. 
- **Solusi**: Hanya `btn.getEl().dom.click()` yang terdaftar mendengarkan *native DOM MouseEvent*, sehingga simulasi murni JS pada elemen root milik Ext akan berhasil memicu postback server.

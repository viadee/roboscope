import { test, expect } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { crc32 } from 'node:zlib';
import { loginViaApi } from '../helpers';

/**
 * V14.3 + V14.4 — export a report's results as CSV/JSON and delete a single
 * report, against the real backend (upload → export → delete → gone).
 */
const API = 'http://localhost:8000/api/v1';

const OUTPUT_XML = `<?xml version="1.0" encoding="UTF-8"?>
<robot generator="Robot 7.0" generated="2026-01-01T12:00:00.000000">
  <suite id="s1" name="E2E Export Suite">
    <test id="s1-t1" name="Passing Test" line="5">
      <status status="PASS" start="2026-01-01T12:00:00.000000" elapsed="0.5"/>
    </test>
    <test id="s1-t2" name="=Formula Test" line="9">
      <status status="FAIL" start="2026-01-01T12:00:01.000000" elapsed="0.5">boom, "quoted"</status>
    </test>
    <status status="FAIL" start="2026-01-01T12:00:00.000000" elapsed="1.5"/>
  </suite>
</robot>`;

/** Minimal single-entry STORED zip (no compression) — no extra deps. */
function zipSingle(name: string, content: string): Buffer {
  const data = Buffer.from(content, 'utf-8');
  const nameBuf = Buffer.from(name);
  const crc = crc32(data);
  const local = Buffer.alloc(30);
  local.writeUInt32LE(0x04034b50, 0);
  local.writeUInt16LE(20, 4);
  local.writeUInt32LE(crc, 14);
  local.writeUInt32LE(data.length, 18);
  local.writeUInt32LE(data.length, 22);
  local.writeUInt16LE(nameBuf.length, 26);
  const central = Buffer.alloc(46);
  central.writeUInt32LE(0x02014b50, 0);
  central.writeUInt16LE(20, 4);
  central.writeUInt16LE(20, 6);
  central.writeUInt32LE(crc, 16);
  central.writeUInt32LE(data.length, 20);
  central.writeUInt32LE(data.length, 24);
  central.writeUInt16LE(nameBuf.length, 28);
  const localLen = local.length + nameBuf.length + data.length;
  const end = Buffer.alloc(22);
  end.writeUInt32LE(0x06054b50, 0);
  end.writeUInt16LE(1, 8);
  end.writeUInt16LE(1, 10);
  end.writeUInt32LE(central.length + nameBuf.length, 12);
  end.writeUInt32LE(localLen, 16);
  return Buffer.concat([local, nameBuf, data, central, nameBuf, end]);
}

test.describe('Report export + single delete', () => {
  test('export CSV/JSON, then delete the report', async ({ page }) => {
    await loginViaApi(page);
    const token = await page.evaluate(() => localStorage.getItem('access_token'));
    const headers = { Authorization: `Bearer ${token}` };

    const upload = await page.request.post(`${API}/reports/upload`, {
      headers,
      multipart: {
        file: { name: 'e2e-export.zip', mimeType: 'application/zip', buffer: zipSingle('output.xml', OUTPUT_XML) },
      },
    });
    expect(upload.status()).toBe(201);
    const reportId: number = (await upload.json()).report.id;

    await page.goto(`/reports/${reportId}`);

    const [csv] = await Promise.all([
      page.waitForEvent('download'),
      page.getByTestId('export-csv').click(),
    ]);
    expect(csv.suggestedFilename()).toBe(`report_${reportId}_results.csv`);
    const csvText = readFileSync(await csv.path(), 'utf-8');
    expect(csvText.split('\n')[0]).toContain('suite_name,test_name,long_name,status');
    expect(csvText).toContain("'=Formula Test");

    const [json] = await Promise.all([
      page.waitForEvent('download'),
      page.getByTestId('export-json').click(),
    ]);
    expect(json.suggestedFilename()).toBe(`report_${reportId}_results.json`);

    page.once('dialog', (d) => d.accept());
    await page.getByTestId('delete-report').click();
    await expect(page).toHaveURL(/\/runs/);

    await page.reload();
    const gone = await page.request.get(`${API}/reports/${reportId}`, { headers });
    expect(gone.status()).toBe(404);
  });
});

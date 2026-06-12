// Auto-generate a Chart.js chart from a rendered markdown table.
// Doughnut for small single-series tables, grouped bar for comparisons,
// horizontal bar for long tables.

function chartFromTable(tableEl, canvas) {
  if (!tableEl || !tableEl.querySelectorAll || !canvas) return;

  const headers = [];
  const rows = [];
  tableEl.querySelectorAll('thead th').forEach(th => headers.push(th.textContent.trim()));
  tableEl.querySelectorAll('tbody tr').forEach(tr => {
    const cells = [];
    tr.querySelectorAll('td').forEach(td => cells.push(td.textContent.trim()));
    if (cells.length) rows.push(cells);
  });
  if (!headers.length || !rows.length) return;

  const parseNum = s => parseFloat((s || '').replace(/[$£€,\s]/g, '')) || 0;

  // Filter out section headers (no numbers) and total/summary rows
  const dataRows = rows.filter(r => {
    if (!r[0]) return false;
    const label = r[0].toLowerCase().trim();
    if (/^(total|sum|grand total|subtotal)/i.test(label)) return false;
    const nums = r.slice(1).filter(c => parseNum(c) !== 0);
    return nums.length > 0;
  });
  if (!dataRows.length) return;

  // Clean up labels: remove leading "- " or "· " prefixes
  const labels = dataRows.map(r => (r[0] || '').replace(/^[-·•]\s*/, '').trim());

  // Find ALL numeric columns (at least 30% of rows have a nonzero value)
  const numCols = [];
  for (let c = 1; c < headers.length; c++) {
    const numCount = dataRows.filter(r => parseNum(r[c]) !== 0).length;
    if (numCount >= dataRows.length * 0.3) numCols.push(c);
  }
  if (!numCols.length) return;

  const colors = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#06b6d4', '#84cc16', '#f97316', '#6366f1'];
  const isComparison = numCols.length >= 2;
  const isFewItems = dataRows.length <= 6 && !isComparison;
  const useHorizontal = dataRows.length > 8;

  // Build datasets
  const datasets = [];
  if (isComparison) {
    numCols.forEach((col, i) => {
      datasets.push({
        label: headers[col] || 'Series ' + (i + 1),
        data: dataRows.map(r => parseNum(r[col])),
        backgroundColor: colors[i % colors.length],
        borderColor: colors[i % colors.length],
        borderWidth: 1,
      });
    });
  } else {
    const col = numCols[0];
    datasets.push({
      label: headers[col] || 'Value',
      data: dataRows.map(r => parseNum(r[col])),
      backgroundColor: isFewItems ? colors.slice(0, dataRows.length) : colors[0],
      borderColor: isFewItems ? 'rgba(0,0,0,0.2)' : colors[0],
      borderWidth: 1,
    });
  }

  const chartType = isFewItems ? 'doughnut' : 'bar';

  canvas.style.display = 'block';
  canvas.height = useHorizontal ? Math.max(300, dataRows.length * 28 + 80) : 250;
  canvas.style.maxWidth = useHorizontal ? '100%' : '500px';

  const existing = Chart.getChart(canvas);
  if (existing) existing.destroy();

  // Build scale config based on orientation
  let scales;
  if (chartType === 'bar') {
    if (useHorizontal) {
      scales = {
        x: { beginAtZero: true, ticks: { color: '#94a3b8', callback: v => '$' + Number(v).toLocaleString() }, grid: { color: 'rgba(148,163,184,0.1)' } },
        y: { ticks: { color: '#e2e8f0', font: { size: 11 } }, grid: { display: false } },
      };
    } else {
      scales = {
        y: { beginAtZero: true, ticks: { color: '#94a3b8', callback: v => '$' + Number(v).toLocaleString() }, grid: { color: 'rgba(148,163,184,0.1)' } },
        x: { ticks: { color: '#e2e8f0', font: { size: 11 }, maxRotation: 45 }, grid: { display: false } },
      };
    }
  }

  new Chart(canvas, {
    type: chartType,
    data: { labels, datasets },
    options: {
      responsive: true,
      indexAxis: useHorizontal ? 'y' : 'x',
      plugins: {
        legend: { display: isComparison || isFewItems, position: isFewItems ? 'right' : 'top', labels: { color: '#94a3b8', font: { size: 11 } } },
        title: { display: false },
        tooltip: { callbacks: { label: ctx => {
          const val = useHorizontal ? (ctx.parsed.x || 0) : (ctx.parsed.y || ctx.parsed || 0);
          return ctx.dataset.label + ': $' + Number(val).toLocaleString();
        } } },
      },
      scales,
    }
  });
}

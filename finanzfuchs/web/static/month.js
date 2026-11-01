// The month chart: cumulative spending on the variable budgets against an even pace.
(() => {
  "use strict";
  const data = JSON.parse(document.getElementById("chart-data").textContent);
  const element = document.getElementById("month-chart");
  if (!element || typeof echarts === "undefined") return;
  const euro = new Intl.NumberFormat("de-DE", { style: "currency", currency: "EUR", maximumFractionDigits: 0 });
  const css = name => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  const chart = echarts.init(element, null, { renderer: "svg" });
  const highest = Math.max(data.planned, ...data.actual, 1);
  // A round top value, so the axis never ends on a label like "1.092".
  const step = 10 ** Math.floor(Math.log10(highest));
  const axisMax = Math.ceil((highest * 1.05) / (step / 2)) * (step / 2);

  function render() {
    const narrow = element.clientWidth < 520;
    chart.setOption({
      textStyle: { fontFamily: "-apple-system, BlinkMacSystemFont, Segoe UI, system-ui, sans-serif", color: css("--text-secondary") },
      grid: { left: narrow ? 52 : 60, right: 64, top: 16, bottom: 28 },
      tooltip: {
        trigger: "axis",
        backgroundColor: css("--surface-1"), borderColor: css("--border"),
        textStyle: { color: css("--text-primary") },
        formatter: points => {
          const day = points[0].axisValue;
          const rows = points.filter(p => p.value !== undefined && p.value !== null)
            .map(p => `${p.seriesName}: <b>${euro.format(p.value)}</b>`).join("<br>");
          return `<b>${day}.</b><br>${rows}`;
        },
      },
      xAxis: {
        type: "category", data: data.days, boundaryGap: false,
        axisLabel: { color: css("--text-muted"), interval: narrow ? 6 : 2 },
        axisLine: { lineStyle: { color: css("--border") } }, axisTick: { show: false },
      },
      yAxis: {
        type: "value", max: axisMax,
        axisLabel: { color: css("--text-muted"), formatter: value => value >= 1000 ? `${(value / 1000).toLocaleString("de-DE", { maximumFractionDigits: 1 })} T€` : `${value} €` },
        splitLine: { lineStyle: { color: css("--grid") } },
      },
      series: [
        { name: "Plan-Tempo", type: "line", data: data.pace, symbol: "none", lineStyle: { width: 2, type: [6, 4], color: css("--text-muted") } },
        {
          name: "Ist", type: "line", data: data.actual, symbol: "none", smooth: 0.2,
          lineStyle: { width: 3, color: css("--expense") },
          areaStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: css("--expense") + "40" }, { offset: 1, color: css("--expense") + "00" }]) },
          endLabel: { show: data.actual.length > 0, formatter: p => euro.format(p.value), color: css("--text-primary"), fontWeight: 600 },
        },
      ],
    }, true);
  }

  render();
  window.addEventListener("resize", () => { chart.resize(); render(); });
  matchMedia("(prefers-color-scheme: dark)").addEventListener("change", render);
})();

// Fixed income and debits: remember which groups were opened.
(() => {
  "use strict";
  const STORAGE_KEY = "finanzfuchs-open-groups";
  const read = () => { try { return JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]"); } catch (error) { return []; } };
  const opened = new Set(read());
  document.querySelectorAll("details.check-group").forEach(group => {
    group.open = opened.has(group.dataset.group);
    group.addEventListener("toggle", () => {
      if (group.open) opened.add(group.dataset.group); else opened.delete(group.dataset.group);
      try { localStorage.setItem(STORAGE_KEY, JSON.stringify([...opened])); } catch (error) { /* private mode: not remembered */ }
    });
  });
})();

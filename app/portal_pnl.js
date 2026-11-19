(function () {
  const data = JSON.parse(document.getElementById("pv-data").textContent);
  data.bases = (data.bases || []).map((row) => ({
    ...row,
    startKey: keyFromIso(row.start),
    endKey: keyFromIso(row.end),
  }));
  const mount = document.getElementById("pv-mount");
  const copy = data.copy;
  const nowMs = Date.parse(data.now);
  const venueById = Object.fromEntries(data.venues.map((venue) => [venue.id, venue]));
  const weekdayIndex = { Sun: 0, Mon: 1, Tue: 2, Wed: 3, Thu: 4, Fri: 5, Sat: 6 };
  let chartPoints = [];
  let hotIdx = null;

  const todayParts = zonedParts(nowMs);
  const today = { y: todayParts.y, m: todayParts.m, d: todayParts.d };
  const state = {
    timeframe: "Monthly",
    venue: "ALL",
    strategy: "ALL",
    year: today.y,
    month: today.m,
    unit: "USD",
    overlay: "CUMULATIVE",
    detailKey: null,
  };

  mount.addEventListener("click", onClick);
  mount.addEventListener("change", onChange);
  mount.addEventListener("mousemove", onMove);
  mount.addEventListener("mouseleave", () => setHot(null));
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && state.detailKey) {
      state.detailKey = null;
      render();
    }
  });
  render();

  function onClick(event) {
    const el = event.target.closest("[data-act]");
    if (!el || !mount.contains(el)) return;
    const act = el.dataset.act;
    if (act === "tf") {
      state.timeframe = el.dataset.tf;
      state.detailKey = null;
    } else if (act === "venue") {
      state.venue = el.dataset.id;
      state.detailKey = null;
    } else if (act === "prev") {
      shiftPeriod(-1);
    } else if (act === "next") {
      if (!nextDisabled()) shiftPeriod(1);
    } else if (act === "unit") {
      state.unit = el.dataset.unit;
    } else if (act === "overlay") {
      state.overlay = el.dataset.overlay;
    } else if (act === "clear") {
      state.venue = "ALL";
      state.strategy = "ALL";
      state.detailKey = null;
    } else if (act === "bar" || act === "day") {
      openPoint(el.dataset.key);
      return;
    } else if (act === "close" || (act === "backdrop" && event.target === el)) {
      state.detailKey = null;
    } else {
      return;
    }
    render();
  }

  function onChange(event) {
    const el = event.target;
    if (el.dataset.act === "year") {
      state.year = Number(el.value);
      if (state.year === today.y && state.month > today.m) state.month = today.m;
      state.detailKey = null;
      render();
    } else if (el.dataset.act === "month") {
      state.month = Number(el.value);
      state.detailKey = null;
      render();
    } else if (el.dataset.act === "strategy") {
      state.strategy = el.value;
      state.detailKey = null;
      render();
    }
  }

  function onMove(event) {
    const bar = event.target.closest("[data-idx]");
    if (!bar || !mount.contains(bar)) {
      setHot(null);
      return;
    }
    setHot(Number(bar.dataset.idx), event);
  }

  function setHot(idx, event) {
    hotIdx = idx;
    mount.querySelectorAll("[data-idx]").forEach((el) => {
      el.classList.toggle("is-hot", idx !== null && Number(el.dataset.idx) === idx);
    });
    const tip = mount.querySelector("#pv-tip");
    if (!tip) return;
    const item = idx === null ? null : chartPoints[idx];
    if (!item || item.future) {
      tip.hidden = true;
      return;
    }
    tip.hidden = false;
    tip.innerHTML =
      `<div class="pv-tip-h"><span>${esc(item.sub)}</span><span>${item.count} ${esc(copy.trades)}</span></div>` +
      tipRow(copy.periodPnl, money(item.pnl), tone(item.pnl)) +
      tipRow(copy.volume, volume(item.volume), "vol") +
      tipRow(copy.cumulative, item.cumulative === null ? "—" : money(item.cumulative), "cum");
    if (!event) return;
    const frame = tip.parentElement.getBoundingClientRect();
    const x = event.clientX - frame.left;
    tip.style.left = Math.min(Math.max(x, 90), frame.width - 90) + "px";
  }

  function tipRow(label, value, kind) {
    return `<div class="pv-tip-r"><span>${esc(label)}</span><b class="${kind}">${esc(value)}</b></div>`;
  }

  function openPoint(key) {
    const item = chartPoints.find((point) => point.key === key);
    if (!item || item.future) return;
    if (state.timeframe === "Annually") {
      state.month = item.month;
      state.year = item.year;
      state.timeframe = "Monthly";
      state.detailKey = null;
      render();
      return;
    }
    if (state.timeframe === "Monthly") {
      state.detailKey = key;
      render();
    }
  }

  function shiftPeriod(dir) {
    if (state.timeframe === "Annually") {
      state.year += dir;
    } else if (state.timeframe === "Monthly") {
      const next = state.month + dir;
      if (next < 1) {
        state.month = 12;
        state.year -= 1;
      } else if (next > 12) {
        state.month = 1;
        state.year += 1;
      } else {
        state.month = next;
      }
    }
    state.detailKey = null;
  }

  function nextDisabled() {
    if (state.timeframe === "Monthly") return state.year > today.y || (state.year === today.y && state.month >= today.m);
    if (state.timeframe === "Annually") return state.year >= today.y;
    return true;
  }

  function render() {
    const model = buildModel();
    chartPoints = model.points;
    hotIdx = null;
    mount.innerHTML = page(model);
  }

  function buildModel() {
    const rows = data.trades.filter(selected);
    if (state.timeframe === "Daily") return rollingHours(rows);
    if (state.timeframe === "Weekly") return rollingDays(rows);
    if (state.timeframe === "Annually") return yearPoints(rows);
    return monthPoints(rows);
  }

  function selected(trade) {
    if (state.venue !== "ALL" && trade.venue !== state.venue) return false;
    if (state.strategy !== "ALL" && trade.strategy !== state.strategy) return false;
    return true;
  }

  function monthPoints(rows) {
    const y = state.year;
    const m = state.month;
    const dim = new Date(Date.UTC(y, m, 0)).getUTCDate();
    const points = [];
    let cumulative = 0;
    for (let day = 1; day <= dim; day++) {
      const future = cmp({ y, m, d: day }, today) > 0;
      const dayRows = future ? [] : rows.filter((trade) => onDay(trade, y, m, day));
      const stats = summarize(dayRows);
      if (!future && stats.pnl !== null) cumulative += stats.pnl;
      points.push(point({
        label: String(day),
        sub: `${y}/${pad(m)}/${pad(day)}${sameDay(y, m, day) ? " (Today)" : ""}`,
        pnl: future ? 0 : stats.pnl,
        volume: future ? 0 : stats.volume,
        cumulative: future || stats.pnl === null ? null : cumulative,
        future,
        closed: future ? [] : stats.closed,
        wins: stats.wins,
        losses: stats.losses,
        key: `d:${y}-${m}-${day}`,
        dateStr: `${y}/${pad(m)}/${pad(day)}`,
        isToday: sameDay(y, m, day),
        dow: weekdayOf(y, m, day),
      }));
    }
    const active = points.filter((item) => !item.future);
    return {
      points,
      kpis: kpis(active, active.length || 1, monthNote(y, m)),
      kind: "month",
      title: copy.monthTitle.replace("{year}", y).replace("{month}", m),
      calendar: points,
      firstDow: weekdayOf(y, m, 1),
    };
  }

  function yearPoints(rows) {
    const points = [];
    let cumulative = 0;
    for (let month = 1; month <= 12; month++) {
      const future = state.year > today.y || (state.year === today.y && month > today.m);
      const monthRows = future ? [] : rows.filter((trade) => inMonth(trade, state.year, month));
      const stats = summarize(monthRows);
      if (!future && stats.pnl !== null) cumulative += stats.pnl;
      const count = stats.closed.length;
      points.push(point({
        label: copy.monthShort.replace("{month}", month),
        sub: `${state.year} ${copy.monthShort.replace("{month}", month)}`,
        pnl: future ? 0 : stats.pnl,
        volume: future ? 0 : stats.volume,
        cumulative: future || stats.pnl === null ? null : cumulative,
        future,
        closed: future ? [] : stats.closed,
        wins: stats.wins,
        losses: stats.losses,
        key: `y:${state.year}-${month}`,
        month,
        year: state.year,
        winRate: count ? (stats.wins / count) * 100 : 0,
      }));
    }
    const active = points.filter((item) => !item.future);
    return {
      points,
      kpis: kpis(active, active.length || 1, yearNote()),
      kind: "year",
      title: copy.yearTitle.replace("{year}", state.year),
    };
  }

  function rollingHours(rows) {
    const points = [];
    let cumulative = 0;
    const buckets = new Map();
    for (let i = 23; i >= 0; i--) {
      const stamp = nowMs - i * 3600000;
      const parts = zonedParts(stamp);
      const key = `${parts.y}-${parts.m}-${parts.d}-${parts.h}`;
      if (!buckets.has(key)) buckets.set(key, { parts, rows: [] });
    }
    rows.forEach((trade) => {
      const parts = zonedParts(Date.parse(trade.ts));
      const key = `${parts.y}-${parts.m}-${parts.d}-${parts.h}`;
      const bucket = buckets.get(key);
      if (bucket) bucket.rows.push(trade);
    });
    buckets.forEach((bucket, key) => {
      const stats = summarize(bucket.rows);
      if (stats.pnl !== null) cumulative += stats.pnl;
      const label = `${pad(bucket.parts.h)}:00`;
      points.push(point({
        label,
        sub: `${bucket.parts.m}/${bucket.parts.d} ${label}`,
        pnl: stats.pnl,
        volume: stats.volume,
        cumulative: stats.pnl === null ? null : cumulative,
        future: false,
        closed: stats.closed,
        wins: stats.wins,
        losses: stats.losses,
        key: `h:${key}`,
      }));
    });
    const closed = points.flatMap((item) => item.closed);
    return {
      points,
      kpis: kpis(points, 1, copy.rollingDay),
      kind: "list",
      title: copy.dayTitle,
      list: closed,
      listTitle: copy.dayList,
    };
  }

  function rollingDays(rows) {
    const points = [];
    let cumulative = 0;
    const closed = [];
    for (let offset = 6; offset >= 0; offset--) {
      const date = addDays(today, -offset);
      const dayRows = rows.filter((trade) => onDay(trade, date.y, date.m, date.d));
      const stats = summarize(dayRows);
      if (stats.pnl !== null) cumulative += stats.pnl;
      const label = `${date.m}/${date.d}`;
      points.push(point({
        label,
        sub: `${date.y}/${pad(date.m)}/${pad(date.d)}${offset === 0 ? " (Today)" : ""}`,
        pnl: stats.pnl,
        volume: stats.volume,
        cumulative: stats.pnl === null ? null : cumulative,
        future: false,
        closed: stats.closed,
        wins: stats.wins,
        losses: stats.losses,
        key: `w:${date.y}-${date.m}-${date.d}`,
      }));
      closed.push(...stats.closed);
    }
    return {
      points,
      kpis: kpis(points, 7, copy.rollingWeek),
      kind: "list",
      title: copy.weekTitle,
      list: closed,
      listTitle: copy.weekList,
    };
  }

  function point(raw) {
    const count = raw.closed.length;
    return {
      ...raw,
      count,
      pnl: raw.pnl === null ? null : round2(raw.pnl),
      volume: raw.volume,
      cumulative: raw.cumulative === null ? null : round2(raw.cumulative),
    };
  }

  function kpis(points, units, note) {
    let net = 0;
    let totalVolume = 0;
    let wins = 0;
    let losses = 0;
    let gross = 0;
    let loss = 0;
    let peak = 0;
    let running = 0;
    let maxDD = 0;
    let missing = false;
    const closed = [];
    points.forEach((item) => {
      totalVolume += item.volume;
      wins += item.wins;
      losses += item.losses;
      closed.push(...item.closed);
      if (item.pnl === null) {
        missing = true;
        return;
      }
      net += item.pnl;
      running += item.pnl;
      if (running > peak) peak = running;
      const drop = running - peak;
      if (drop < maxDD) maxDD = drop;
    });
    closed.forEach((trade) => {
      const pnl = shownPnl(trade);
      if (pnl === null || pnl === undefined) return;
      if (pnl > 0) gross += pnl;
      else if (pnl < 0) loss += Math.abs(pnl);
    });
    const count = wins + losses;
    return {
      net: missing ? null : round2(net),
      totalVolume,
      avgTrade: count ? totalVolume / count : 0,
      avgPeriod: totalVolume / units,
      note,
      winRate: count ? (wins / count) * 100 : 0,
      wins,
      losses,
      profitFactor: loss > 0 ? gross / loss : gross > 0 ? 9.99 : 0,
      avgWin: wins ? gross / wins : 0,
      avgLoss: losses ? loss / losses : 0,
      maxDD: missing ? null : round2(maxDD),
      periodUnit: state.timeframe === "Annually" ? copy.perMonth : copy.perDay,
    };
  }

  function page(model) {
    return (
      controls() +
      cards(model.kpis) +
      chartCard(model) +
      bottom(model) +
      drawer()
    );
  }

  function controls() {
    const frames = ["Daily", "Weekly", "Monthly", "Annually"].map((tf) => {
      const label = copy.frames[tf];
      return `<button type="button" data-act="tf" data-tf="${tf}" class="${state.timeframe === tf ? "is-on" : ""}">${esc(label)}</button>`;
    }).join("");
    const period = state.timeframe === "Monthly" || state.timeframe === "Annually" ? periodPicker() : (
      `<div class="pv-asof"><span class="pv-dot"></span><span>${esc(copy.asOfBasis)} <strong>${esc(state.timeframe === "Daily" ? copy.last24 : copy.last7)}</strong></span></div>`
    );
    const venues = data.venues.map((venue) => {
      const on = state.venue === venue.id;
      const badge = venue.type ? `<em class="${venue.type === "DEX" ? "dex" : "cex"}">${esc(venue.type)}</em>` : "";
      return `<button type="button" data-act="venue" data-id="${esc(venue.id)}" class="${on ? "is-on" : ""}"><i style="background:${venue.color}"></i>${esc(venue.label)}${badge}</button>`;
    }).join("");
    const strategies = data.strategies.map((item) => `<option value="${esc(item.id)}"${item.id === state.strategy ? " selected" : ""}>${esc(item.label)}</option>`).join("");
    const clear = state.venue !== "ALL" || state.strategy !== "ALL"
      ? `<button type="button" class="pv-clear" data-act="clear">${esc(copy.clear)}</button>`
      : "";
    return `<section class="pv-card pv-controls">
      <div class="pv-row">
        <div class="pv-row-l">
          <div class="pv-seg">${frames}</div>
          ${period}
        </div>
        <div class="pv-unit">
          <span>${esc(copy.unit)}</span>
          <div class="pv-seg">
            <button type="button" data-act="unit" data-unit="USD" class="${state.unit === "USD" ? "is-usd" : ""}">$ (USD)</button>
            <button type="button" data-act="unit" data-unit="PERCENT" class="${state.unit === "PERCENT" ? "is-pct" : ""}">% (ROI)</button>
          </div>
        </div>
      </div>
      <div class="pv-filters">
        <div class="pv-pills"><span class="pv-k">${esc(copy.venues)}</span>${venues}</div>
        <label class="pv-strategy"><span class="pv-k">${esc(copy.strategy)}</span>
          <select data-act="strategy">${strategies}</select>
        </label>
        ${clear}
      </div>
      <p class="pv-basis">${esc(basisNote())}</p>
    </section>`;
  }

  function periodPicker() {
    const years = yearChoices().map((year) => `<option value="${year}"${year === state.year ? " selected" : ""}>${year}</option>`).join("");
    const months = state.timeframe === "Monthly" ? `<select data-act="month">${monthChoices()}</select>` : "";
    return `<div class="pv-period">
      <button type="button" data-act="prev" aria-label="${esc(copy.previous)}">${chevron("left")}</button>
      <span class="pv-cal">${icon("calendar")}<select data-act="year">${years}</select>${months}</span>
      <button type="button" data-act="next" ${nextDisabled() ? "disabled" : ""} aria-label="${esc(copy.next)}">${chevron("right")}</button>
    </div>`;
  }

  function yearChoices() {
    let minY = today.y;
    data.trades.forEach((trade) => {
      const year = zonedParts(Date.parse(trade.ts)).y;
      if (year < minY) minY = year;
    });
    const years = [];
    for (let year = minY; year <= today.y; year++) years.push(year);
    if (!years.length) years.push(today.y);
    return years;
  }

  function monthChoices() {
    let html = "";
    for (let month = 1; month <= 12; month++) {
      const disabled = state.year === today.y && month > today.m;
      html += `<option value="${month}"${month === state.month ? " selected" : ""}${disabled ? " disabled" : ""}>${month}</option>`;
    }
    return html;
  }

  function cards(stats) {
    return `<section class="pv-kpis">
      ${kpi(copy.net, money(stats.net), tone(stats.net), esc(stats.note), stats.net === null ? "pf" : stats.net >= 0 ? "up" : "down")}
      ${kpi(copy.totalVolume, volume(stats.totalVolume), "", `${esc(copy.avgTrade)} ${esc(volume(stats.avgTrade, true))} · ${esc(volume(stats.avgPeriod, true))}/${esc(stats.periodUnit)}`, "vol")}
      ${kpi(copy.winRate, `${stats.winRate.toFixed(1)}%`, "", `<b class="up">${stats.wins}W</b> / <b class="down">${stats.losses}L</b> <span>(${stats.wins + stats.losses})</span>`, "win")}
      ${kpi(copy.profitFactor, stats.profitFactor.toFixed(2), "", `${esc(copy.avgWin)} ${esc(money(stats.avgWin, false))} / ${esc(copy.avgLoss)} ${esc(money(stats.avgLoss, false))}`, "pf")}
      ${kpi(copy.maxDD, money(stats.maxDD), stats.maxDD !== null && stats.maxDD < 0 ? "down" : "", esc(copy.maxDDHint), "dd")}
    </section>`;
  }

  function kpi(label, value, valueClass, note, kind) {
    return `<article class="pv-card pv-kpi"><header><span>${esc(label)}</span><i class="pv-ico ${kind}">${icon(kind)}</i></header><strong class="${valueClass}">${esc(value)}</strong><p>${note}</p></article>`;
  }

  function chartCard(model) {
    const chips = [
      state.venue !== "ALL" ? `<em class="venue">${esc(venueById[state.venue] ? venueById[state.venue].label : state.venue)}</em>` : "",
      state.strategy !== "ALL" ? `<em class="strategy">${esc(state.strategy)}</em>` : "",
    ].join("");
    const hint = state.timeframe === "Annually" ? copy.yearHint : copy.chartHint;
    return `<section class="pv-card pv-chart-card">
      <header>
        <div><h3>${icon("chart")} ${esc(model.title)} ${chips}</h3><p>${esc(hint)}</p></div>
        <div class="pv-legend-wrap">
          <div class="pv-seg">
            <button type="button" data-act="overlay" data-overlay="CUMULATIVE" class="${state.overlay === "CUMULATIVE" ? "is-on" : ""}">${esc(copy.overlayPnl)}</button>
            <button type="button" data-act="overlay" data-overlay="VOLUME" class="${state.overlay === "VOLUME" ? "is-on" : ""}">${esc(copy.overlayVol)}</button>
          </div>
          <div class="pv-legend"><i class="g"></i>${esc(copy.profit)}<i class="r"></i>${esc(copy.loss)}<i class="p"></i>${esc(copy.volKey)}${state.overlay === "CUMULATIVE" ? `<i class="line"></i>${esc(copy.cumKey)}` : ""}</div>
        </div>
      </header>
      <div class="pv-plot">${chartSvg(model.points)}<div id="pv-tip" class="pv-tip" hidden></div></div>
    </section>`;
  }

  function chartSvg(points) {
    const width = 960;
    const height = 285;
    const padLeft = 68;
    const padRight = state.overlay === "VOLUME" ? 64 : 28;
    const padTop = 28;
    const padBottom = 38;
    const plotW = width - padLeft - padRight;
    const plotH = height - padTop - padBottom;
    let min = 0;
    let max = 0;
    let topVol = 0;
    points.forEach((item) => {
      if (item.future || item.pnl === null) return;
      min = Math.min(min, item.pnl);
      max = Math.max(max, item.pnl);
      if (state.overlay === "CUMULATIVE" && item.cumulative !== null) {
        min = Math.min(min, item.cumulative);
        max = Math.max(max, item.cumulative);
      }
      topVol = Math.max(topVol, item.volume || 0);
    });
    if (max === min) {
      max += 1;
      min -= 1;
    }
    const range = Math.max(max - min, 1);
    const paddedMax = max + range * 0.16;
    const paddedMin = min - range * 0.16;
    const span = paddedMax - paddedMin;
    const toY = (value) => padTop + ((paddedMax - value) / span) * plotH;
    const volMax = Math.max(topVol, 1) * 1.25;
    const toVolY = (value) => padTop + plotH - (value / volMax) * plotH;
    const step = plotW / Math.max(points.length, 1);
    const barW = Math.max(6, Math.min(26, step * 0.52));
    const zeroY = toY(0);
    let grid = "";
    for (let i = 0; i <= 4; i++) {
      const ratio = i / 4;
      const y = padTop + ratio * plotH;
      const val = paddedMax - ratio * (paddedMax - paddedMin);
      const volVal = volMax * (1 - ratio);
      grid += `<line x1="${padLeft}" y1="${y}" x2="${width - padRight}" y2="${y}" stroke="#1e293b" stroke-dasharray="4 4"/>`;
      grid += `<text x="${padLeft - 8}" y="${y + 4}" text-anchor="end" class="axis">${esc(axisMoney(val))}</text>`;
      if (state.overlay === "VOLUME") {
        grid += `<text x="${width - padRight + 8}" y="${y + 4}" class="axis vol">${esc(volume(volVal, true))}</text>`;
      }
    }
    let vols = "";
    let bars = "";
    let labels = "";
    const segments = [[]];
    points.forEach((item, idx) => {
      const x = padLeft + idx * step + step / 2;
      if (!item.future && item.volume) {
        const volW = state.overlay === "VOLUME" ? barW * 1.45 : barW * 1.25;
        const y = toVolY(item.volume);
        vols += `<rect x="${x - volW / 2}" y="${y}" width="${volW}" height="${Math.max(padTop + plotH - y, 2)}" rx="3" class="vol-bar"/>`;
      }
      if (item.future) {
        bars += `<rect x="${x - barW / 2}" y="${padTop}" width="${barW}" height="${plotH}" rx="3" class="future"/>`;
      } else if (item.pnl === null) {
        bars += `<g data-idx="${idx}" data-act="bar" data-key="${esc(item.key)}"><rect class="hit" x="${padLeft + idx * step}" y="${padTop}" width="${step}" height="${plotH}"></rect></g>`;
      } else {
        const y = toY(item.pnl);
        const barY = item.pnl >= 0 ? y : zeroY;
        const barH = Math.max(Math.abs(y - zeroY), item.pnl === 0 ? 2 : 3);
        const fill = item.pnl > 0 ? "pos" : item.pnl < 0 ? "neg" : "flat";
        bars += `<g data-idx="${idx}" data-act="bar" data-key="${esc(item.key)}"><rect class="hit" x="${padLeft + idx * step}" y="${padTop}" width="${step}" height="${plotH}"></rect><rect class="pv-pnl ${fill}" x="${x - barW / 2}" y="${barY}" width="${barW}" height="${barH}" rx="3"></rect></g>`;
      }
      if (state.overlay === "CUMULATIVE" && !item.future && item.cumulative !== null) {
        segments[segments.length - 1].push(`${x},${toY(item.cumulative)}`);
      } else if (state.overlay === "CUMULATIVE") {
        segments.push([]);
      }
      const show = points.length <= 14 || idx === 0 || idx === points.length - 1 || (idx + 1) % 3 === 0;
      if (show) labels += `<text x="${x}" y="${height - 10}" text-anchor="middle" class="axis${item.future ? " future-label" : ""}">${esc(item.label)}</text>`;
    });
    let dots = "";
    if (state.overlay === "CUMULATIVE") {
      points.forEach((item, idx) => {
        if (item.future || item.cumulative === null) return;
        const x = padLeft + idx * step + step / 2;
        dots += `<circle cx="${x}" cy="${toY(item.cumulative)}" r="3" class="dot"/>`;
      });
    }
    const polyline = segments.filter((segment) => segment.length > 1).map((segment) => `<polyline fill="none" stroke="url(#pvLine)" stroke-width="2.8" stroke-linecap="round" stroke-linejoin="round" points="${segment.join(" ")}"/>`).join("");
    return `<svg viewBox="0 0 ${width} ${height}" class="pv-chart" data-chart="1">
      <defs>
        <linearGradient id="pvLine" x1="0" y1="0" x2="1" y2="0"><stop offset="0%" stop-color="#9945ff"/><stop offset="100%" stop-color="#80ecff"/></linearGradient>
        <linearGradient id="pvPos" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="#14f195"/><stop offset="100%" stop-color="#14f195" stop-opacity="0.45"/></linearGradient>
        <linearGradient id="pvNeg" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="#ff4d6d" stop-opacity="0.45"/><stop offset="100%" stop-color="#ff4d6d"/></linearGradient>
      </defs>
      ${grid}<line x1="${padLeft}" y1="${zeroY}" x2="${width - padRight}" y2="${zeroY}" stroke="#334155" stroke-width="1.5"/>${vols}${bars}${polyline}${dots}${labels}
    </svg>`;
  }

  function bottom(model) {
    if (model.kind === "month") return calendar(model);
    if (model.kind === "year") return yearCards(model);
    return tradeTable(model.listTitle, model.list);
  }

  function calendar(model) {
    const names = copy.weekdays;
    const heads = names.map((name, idx) => `<div class="${idx === 0 ? "sun" : idx === 6 ? "sat" : ""}">${esc(name)}</div>`).join("");
    let cells = "";
    for (let i = 0; i < model.firstDow; i++) cells += `<div class="pv-empty"></div>`;
    model.calendar.forEach((day) => {
      const style = day.future || day.pnl === null || day.pnl === 0 ? "" : ` style="${cellStyle(day.pnl)}"`;
      const body = day.future
        ? `<div class="pv-blank">—</div>`
        : `<div class="pv-cell-pnl ${tone(day.pnl)}">${esc(money(day.pnl))}</div><div class="pv-cell-vol">${esc(copy.volKey)} ${esc(volume(day.volume, true))}</div><div class="pv-cell-n">${day.count} ${esc(copy.trades)}</div>`;
      cells += `<button type="button" data-act="day" data-key="${esc(day.key)}" ${day.future ? "disabled" : ""} class="pv-day${day.isToday ? " is-today" : ""}${day.future ? " is-future" : ""}"${style}><span>${day.label}${day.isToday ? `<em>TODAY</em>` : ""}</span>${body}</button>`;
    });
    const futureNote = state.year === today.y && state.month === today.m ? `<span class="pv-future-note">${esc(copy.futureDays)}</span>` : "";
    return `<section class="pv-card pv-bottom"><header><div><h3>${icon("calendar")} ${esc(copy.calendarTitle.replace("{year}", state.year).replace("{month}", state.month))}</h3><p>${esc(copy.calendarHint)}</p></div>${futureNote}</header><div class="pv-dow">${heads}</div><div class="pv-cal-grid">${cells}</div></section>`;
  }

  function yearCards(model) {
    const cardsHtml = model.points.map((item) => {
      if (item.future) {
        return `<button type="button" disabled class="pv-month is-future"><b>${item.year} ${esc(item.label)}</b><span>${esc(copy.futureMonth)}</span></button>`;
      }
      return `<button type="button" data-act="bar" data-key="${esc(item.key)}" class="pv-month ${item.pnl === null ? "" : item.pnl >= 0 ? "up-card" : "down-card"}"><span class="pv-month-h"><b>${item.year} ${esc(item.label)}</b><em>${esc(copy.details)}</em></span><strong class="${tone(item.pnl)}">${esc(money(item.pnl))}</strong><span class="vol">${esc(copy.volKey)} ${esc(volume(item.volume, true))}</span><span class="pv-month-f">${esc(copy.winRate)} ${item.winRate.toFixed(1)}% · ${item.count} ${esc(copy.trades)}</span></button>`;
    }).join("");
    return `<section class="pv-card pv-bottom"><header><div><h3>${icon("layers")} ${esc(copy.yearList.replace("{year}", state.year))}</h3><p>${esc(copy.yearHint)}</p></div></header><div class="pv-months">${cardsHtml}</div></section>`;
  }

  function tradeTable(title, rows) {
    const ordered = rows.slice().sort((a, b) => Date.parse(b.ts) - Date.parse(a.ts));
    const shown = ordered.slice(0, 100);
    const body = shown.length
        ? shown.map((trade) => `<tr><td>${esc(clock(trade))}</td><td>${esc(trade.strategy)}</td><td>${esc(trade.pair)}</td><td><span class="side ${trade.side === "LONG" ? "up" : "down"}">${esc(trade.side)}</span></td><td>${esc(venueName(trade.venue))}</td><td class="num vol">${esc(volume(Number(trade.volume)))}</td><td class="num ${tone(shownPnl(trade))}">${esc(money(shownPnl(trade)))}</td></tr>`).join("")
      : `<tr><td colspan="7" class="pv-none">${esc(copy.noTrades)}</td></tr>`;
    const extra = ordered.length > shown.length ? `<p class="pv-more">${esc(copy.showing.replace("{shown}", shown.length).replace("{total}", ordered.length))}</p>` : "";
    return `<section class="pv-card pv-bottom"><header><div><h3>${icon("activity")} ${esc(title)}</h3><p>${esc(copy.listHint)} ${esc(data.asOf)}</p></div><span class="pv-count">${ordered.length} ${esc(copy.executions)}</span></header><div class="pv-table"><table><thead><tr><th>${esc(copy.filledAt)}</th><th>${esc(copy.strategy)}</th><th>${esc(copy.pair)}</th><th>${esc(copy.side)}</th><th>${esc(copy.venues)}</th><th>${esc(copy.volume)}</th><th>${esc(copy.realized)}</th></tr></thead><tbody>${body}</tbody></table></div>${extra}</section>`;
  }

  function drawer() {
    if (!state.detailKey) return "";
    const day = chartPoints.find((item) => item.key === state.detailKey);
    if (!day) return "";
    const chips = [
      day.isToday ? `<em class="today">TODAY</em>` : "",
      state.venue !== "ALL" ? `<em class="venue">${esc(venueName(state.venue))}</em>` : "",
      state.strategy !== "ALL" ? `<em class="strategy">${esc(state.strategy)}</em>` : "",
    ].join("");
    const rows = day.closed.slice().sort((a, b) => Date.parse(b.ts) - Date.parse(a.ts));
    const list = rows.length
      ? rows.map((trade) => `<article class="pv-fill"><header><span><b class="${trade.side === "LONG" ? "up" : "down"}">${esc(trade.side)}</b> ${esc(trade.pair)} <em>${esc(venueName(trade.venue))}</em></span><strong class="${tone(shownPnl(trade))}">${esc(money(shownPnl(trade)))}</strong></header><p><span>${esc(copy.strategy)} ${esc(trade.strategy)}</span><span class="vol">${esc(copy.volKey)} ${esc(volume(Number(trade.volume), true))}</span><span>${esc(clock(trade))}</span></p></article>`).join("")
      : `<p class="pv-none">${esc(copy.noTrades)}</p>`;
    return `<div class="pv-drawer" data-act="backdrop"><aside><header><div><h3>${esc(day.dateStr)} ${chips}</h3><p>${esc(copy.drawerHint)}</p></div><button type="button" data-act="close" aria-label="${esc(copy.close)}">×</button></header><div class="pv-drawer-k"><div><span>${esc(copy.dayPnl)}</span><strong class="${tone(day.pnl)}">${esc(money(day.pnl))}</strong></div><div><span>${esc(copy.dayVol)}</span><strong class="vol">${esc(volume(day.volume, true))}</strong></div><div><span>${esc(copy.winLoss)}</span><strong><b class="up">${day.wins}W</b> / <b class="down">${day.losses}L</b></strong></div></div><div class="pv-fills">${list}</div></aside></div>`;
  }

  function summarize(rows) {
    let pnl = 0;
    let traded = 0;
    let wins = 0;
    let losses = 0;
    const closed = [];
    let missing = false;
    rows.forEach((trade) => {
      traded += Number(trade.volume || 0);
      const value = shownPnl(trade);
      if (value === undefined) {
        missing = true;
        closed.push(trade);
        return;
      }
      if (value === null) return;
      pnl += value;
      if (value > 0) wins += 1;
      else if (value < 0) losses += 1;
      closed.push(trade);
    });
    return { pnl: missing ? null : pnl, volume: traded, wins, losses, closed };
  }

  function shownPnl(trade) {
    if (trade.pnl === null || trade.pnl === undefined || trade.pnl === "") return null;
    const usd = Number(trade.pnl);
    if (state.unit !== "PERCENT") return usd;
    const capital = capitalOn(trade.ts);
    if (capital == null) return undefined;
    return (usd / capital) * 100;
  }

  function capitalOn(ts) {
    const parts = zonedParts(Date.parse(ts));
    const key = parts.y * 10000 + parts.m * 100 + parts.d;
    const row = data.bases.find((item) => key >= item.startKey && key <= item.endKey);
    return row ? row.capital : null;
  }

  function keyFromIso(value) {
    const [year, month, day] = String(value).split("-").map(Number);
    return year * 10000 + month * 100 + day;
  }

  function basisNote() {
    if (!data.bases.length) return copy.roiNone;
    const key = today.y * 10000 + today.m * 100 + today.d;
    const row = data.bases.find((item) => key >= item.startKey && key <= item.endKey);
    if (!row) return copy.roiMissing;
    const amount = `$${Number(row.capital).toLocaleString("en-US", { maximumFractionDigits: 0 })}`;
    const text = copy.roiBasis.replace("{amount}", amount).replace("{start}", row.start).replace("{end}", row.end);
    return data.bases.length > 1 ? `${text} ${copy.roiMore}` : text;
  }

  function onDay(trade, y, m, d) {
    const parts = zonedParts(Date.parse(trade.ts));
    return parts.y === y && parts.m === m && parts.d === d;
  }

  function inMonth(trade, y, m) {
    const parts = zonedParts(Date.parse(trade.ts));
    return parts.y === y && parts.m === m;
  }

  function zonedParts(ms) {
    const fmt = new Intl.DateTimeFormat("en-US", {
      timeZone: data.zone,
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      weekday: "short",
      hourCycle: "h23",
    });
    const parts = {};
    fmt.formatToParts(new Date(ms)).forEach((part) => {
      parts[part.type] = part.value;
    });
    return {
      y: Number(parts.year),
      m: Number(parts.month),
      d: Number(parts.day),
      h: Number(parts.hour === "24" ? "0" : parts.hour),
      min: Number(parts.minute),
      wd: weekdayIndex[parts.weekday] ?? 0,
    };
  }

  function probe(y, m, d) {
    let guess = Date.UTC(y, m - 1, d, 12, 0, 0);
    for (let i = 0; i < 30; i++) {
      const parts = zonedParts(guess);
      if (parts.y === y && parts.m === m && parts.d === d) return guess;
      guess += (cmp({ y, m, d }, parts) > 0 ? 1 : -1) * 3600000;
    }
    return Date.UTC(y, m - 1, d, 12, 0, 0);
  }

  function weekdayOf(y, m, d) {
    return zonedParts(probe(y, m, d)).wd;
  }

  function addDays(date, delta) {
    const next = new Date(Date.UTC(date.y, date.m - 1, date.d + delta));
    return { y: next.getUTCFullYear(), m: next.getUTCMonth() + 1, d: next.getUTCDate() };
  }

  function sameDay(y, m, d) {
    return y === today.y && m === today.m && d === today.d;
  }

  function cmp(a, b) {
    return a.y - b.y || a.m - b.m || a.d - b.d;
  }

  function monthNote(y, m) {
    if (y === today.y && m === today.m) return copy.monthToDate.replace("{day}", today.d);
    return copy.selectedMonth;
  }

  function yearNote() {
    if (state.year === today.y) return copy.yearToDate.replace("{month}", today.m);
    return copy.selectedYear;
  }

  function money(value, showSign) {
    if (value === null || value === undefined || Number.isNaN(Number(value))) return "—";
    const amount = Number(value);
    const sign = amount > 0 ? (showSign === false ? "" : "+") : amount < 0 ? "-" : "";
    const abs = Math.abs(amount);
    if (state.unit === "USD") return `${sign}$${abs.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    return `${sign}${abs.toFixed(2)}%`;
  }

  function axisMoney(value) {
    if (state.unit === "PERCENT") {
      const sign = value < 0 ? "-" : "";
      return `${sign}${Math.abs(value).toFixed(1)}%`;
    }
    const sign = value < 0 ? "-" : "";
    return `${sign}$${Math.abs(Math.round(value)).toLocaleString("en-US")}`;
  }

  function volume(value, compact) {
    const amount = Number(value) || 0;
    if (compact) {
      if (amount >= 1000000) return `$${(amount / 1000000).toFixed(2)}M`;
      if (amount >= 1000) return `$${Math.round(amount / 1000)}k`;
    }
    return `$${Math.round(amount).toLocaleString("en-US")}`;
  }

  function clock(trade) {
    const parts = zonedParts(Date.parse(trade.ts));
    return `${pad(parts.m)}/${pad(parts.d)} ${pad(parts.h)}:${pad(parts.min)}`;
  }

  function venueName(id) {
    return venueById[id] ? venueById[id].label : id;
  }

  function cellStyle(pnl) {
    const intensity = Math.min(Math.abs(pnl) / 800, 1);
    if (pnl > 0) return `background:rgba(20,241,149,${0.06 + intensity * 0.16});border-color:rgba(20,241,149,${0.25 + intensity * 0.4})`;
    return `background:rgba(255,77,109,${0.06 + intensity * 0.16});border-color:rgba(255,77,109,${0.25 + intensity * 0.4})`;
  }

  function tone(value) {
    if (value > 0) return "up";
    if (value < 0) return "down";
    return "";
  }

  function round2(value) {
    return Math.round((value + Number.EPSILON) * 100) / 100;
  }

  function pad(value) {
    return String(value).padStart(2, "0");
  }

  function esc(value) {
    return String(value ?? "").replace(/[&<>"']/g, (ch) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch]));
  }

  function icon(name) {
    const paths = {
      up: '<polyline points="22 7 13.5 15.5 8.5 10.5 2 17"/><polyline points="16 7 22 7 22 13"/>',
      down: '<polyline points="22 17 13.5 8.5 8.5 13.5 2 7"/><polyline points="16 17 22 17 22 11"/>',
      vol: '<path d="M3 3v18h18"/><path d="M18 17V9"/><path d="M13 17V5"/><path d="M8 17v-3"/>',
      win: '<circle cx="12" cy="8" r="7"/><polyline points="8.21 13.89 7 23 12 20 17 23 15.79 13.88"/>',
      pf: '<polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>',
      dd: '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>',
      chart: '<line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/>',
      calendar: '<rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/>',
      layers: '<polygon points="12 2 2 7 12 12 22 7 12 2"/><polyline points="2 17 12 22 22 17"/><polyline points="2 12 12 17 22 12"/>',
      activity: '<polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>',
    };
    return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${paths[name] || ""}</svg>`;
  }

  function chevron(dir) {
    const points = dir === "left" ? "15 18 9 12 15 6" : "9 18 15 12 9 6";
    return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="${points}"/></svg>`;
  }
})();

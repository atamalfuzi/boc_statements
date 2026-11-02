// Statement explorer: a canvas timeline of each announcement day and the chosen statement compared with the one before.
// Data come from data.js (STATEMENTS), written by dashboard.py. No libraries.
(function () {
  var S = STATEMENTS.statements, BAND = STATEMENTS.band, HEIGHT = 240;
  var COLOURS = { hold: "#a8a7a2", hike: "#eb6834", cut: "#2a78d6" }, WORDS = { hold: "Held", hike: "Raised", cut: "Lowered" };
  var MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
  var canvas = document.getElementById("timeline"), ctx = canvas.getContext("2d"), choose = document.getElementById("choose");
  var earlier = document.getElementById("previous"), later = document.getElementById("next");
  var tip = document.createElement("div"), current = S.length - 1;
  tip.className = "tip";
  tip.hidden = true;
  document.body.appendChild(tip);

  function dateText(iso) { var p = iso.split("-"); return +p[2] + " " + MONTHS[p[1] - 1] + " " + p[0]; }
  function bp(x, digits) { return (x > 0 ? "+" : x < 0 ? "−" : "") + Math.abs(x).toFixed(digits === undefined ? 0 : digits) + " bp"; }
  function decisionText(s) {
    if (s.change === null || s.change === 0) return WORDS[s.decision] + " the rate";
    return WORDS[s.decision] + " the rate by " + Math.abs(s.change) + " bp";
  }
  function moveText(s) { return s.move === null ? "No yield move for this date" : "2-year yield " + bp(s.move, 1) + " after the US move (" + bp(s.raw) + " before it)"; }

  var SPAN = 32, PAD = { left: 34, right: 6, top: 10, bottom: 22 };
  function x(i, w) { return PAD.left + (w - PAD.left - PAD.right) * (i + 0.5) / S.length; }
  function y(v) { return PAD.top + (HEIGHT - PAD.top - PAD.bottom) * (SPAN - Math.max(-SPAN, Math.min(SPAN, v))) / (2 * SPAN); }

  function draw() {
    var w = canvas.clientWidth, ratio = window.devicePixelRatio || 1;
    canvas.style.height = HEIGHT + "px";
    canvas.width = Math.round(w * ratio);
    canvas.height = Math.round(HEIGHT * ratio);
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
    ctx.clearRect(0, 0, w, HEIGHT);
    ctx.font = "12px " + getComputedStyle(document.body).fontFamily;
    ctx.textBaseline = "middle";
    ctx.fillStyle = "#eceeed";
    ctx.fillRect(PAD.left, y(BAND), w - PAD.left - PAD.right, y(-BAND) - y(BAND));
    ctx.fillStyle = "#5f6964";
    ctx.textAlign = "right";
    [-30, -15, 0, 15, 30].forEach(function (v) { ctx.fillText(v > 0 ? "+" + v : String(v).replace("-", "−"), PAD.left - 6, y(v)); });
    ctx.strokeStyle = "#5f6964";
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(PAD.left, y(0));
    ctx.lineTo(w - PAD.right, y(0));
    ctx.stroke();
    var bar = Math.max(1.5, (w - PAD.left - PAD.right) / S.length * 0.72);
    S.forEach(function (s, i) {
      if (s.move === null) return;
      ctx.fillStyle = COLOURS[s.decision];
      var top = Math.min(y(s.move), y(0));
      ctx.fillRect(x(i, w) - bar / 2, top, bar, Math.max(1, Math.abs(y(s.move) - y(0))));
    });
    ctx.fillStyle = "#5f6964";
    ctx.textAlign = "center";
    var seen = {};
    S.forEach(function (s, i) {
      var year = +s.date.slice(0, 4);
      if (!seen[year] && year % (w < 520 ? 10 : 5) === 0) { seen[year] = true; ctx.fillText(String(year), x(i, w), HEIGHT - 9); }
    });
    ctx.strokeStyle = "#17201d";
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.moveTo(x(current, w), PAD.top);
    ctx.lineTo(x(current, w), HEIGHT - PAD.bottom);
    ctx.stroke();
  }

  function index(e) {
    var r = canvas.getBoundingClientRect(), f = (e.clientX - r.left - PAD.left) / (r.width - PAD.left - PAD.right);
    return Math.max(0, Math.min(S.length - 1, Math.floor(f * S.length)));
  }
  function hover(e) {
    var s = S[index(e)];
    tip.textContent = dateText(s.date) + "\n" + decisionText(s) + "\n" + moveText(s);
    tip.hidden = false;
    var left = e.pageX + 14;
    if (e.clientX + 14 + tip.offsetWidth > document.documentElement.clientWidth) left = e.pageX - tip.offsetWidth - 14;
    tip.style.left = Math.max(4, left) + "px";
    tip.style.top = e.pageY + 14 + "px";
  }

  function fill(parent, parts) {
    var p = document.createElement("p");
    parts.forEach(function (part, i) {
      var span = document.createElement("span");
      span.className = part[0] ? "added" : "kept";
      span.textContent = part[1];
      if (i) p.appendChild(document.createTextNode(" "));
      p.appendChild(span);
    });
    parent.appendChild(p);
  }

  function show(i, keepHash) {
    current = i;
    var s = S[i], body = document.getElementById("body"), lost = document.getElementById("lost");
    document.getElementById("title").textContent = s.title;
    document.getElementById("facts").textContent = dateText(s.date) + ". " + decisionText(s) + ". " + moveText(s) + ".";
    var notes = [];
    if (s.fed) notes.push("The US Federal Reserve announced a decision the same day, after this statement and before the market close.");
    if (s.report) notes.push("The Monetary Policy Report came out the same morning.");
    var flag = document.getElementById("flag");
    flag.hidden = !notes.length;
    flag.textContent = notes.length ? notes.join(" ") + " The move can't be credited to this statement alone." : "";
    body.textContent = "";
    if (i === 0) {
      var first = document.createElement("p");
      first.textContent = s.parts[0][0][1];
      body.appendChild(first);
    } else {
      s.parts.forEach(function (parts) { fill(body, parts); });
    }
    lost.textContent = "";
    s.lost.forEach(function (t) { var li = document.createElement("li"); li.textContent = t; lost.appendChild(li); });
    document.getElementById("lost-block").hidden = !s.lost.length;
    document.getElementById("source").href = s.url;
    choose.value = String(i);
    earlier.disabled = i === 0;
    later.disabled = i === S.length - 1;
    if (!keepHash) history.replaceState(null, "", "#" + s.date);
    draw();
  }

  S.forEach(function (s, i) {
    var o = document.createElement("option");
    o.value = String(i);
    o.textContent = dateText(s.date) + ": " + decisionText(s).toLowerCase();
    choose.appendChild(o);
  });
  choose.addEventListener("change", function () { show(+choose.value); });
  earlier.addEventListener("click", function () { show(current - 1); });
  later.addEventListener("click", function () { show(current + 1); });
  canvas.addEventListener("pointermove", hover);
  canvas.addEventListener("pointerleave", function () { tip.hidden = true; });
  canvas.addEventListener("click", function (e) { show(index(e)); });
  window.addEventListener("resize", draw);
  function fromHash() {
    var wanted = S.map(function (s) { return s.date; }).indexOf(location.hash.slice(1));
    show(wanted < 0 ? S.length - 1 : wanted, true);
  }
  window.addEventListener("hashchange", fromHash);
  fromHash();
})();

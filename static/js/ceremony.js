/* ================================================================
   Ceremonia final del Tour de France.
   Fase 1: podio animado (1º/2º/3º) + fuegos artificiales.
   Fase 2: "bar chart race" mostrando cómo se sumaron los puntos
           etapa a etapa.
   Autónomo: sin librerías externas.
   ================================================================ */
(function () {
  "use strict";

  var CFG = window.__CEREMONY || {};
  // Clave de sesión y subtítulo son configurables para poder reutilizar la
  // ceremonia en varias competencias (Tour archivado, La Vuelta, futuras).
  var SEEN_KEY = CFG.seenKey || "tdf_ceremony_seen_v1";
  var SUBTITLE = CFG.subtitle || "Tour de France 2026 · ¡Enhorabuena a todos!";

  // ---------------------------------------------------------------
  // Utilidades
  // ---------------------------------------------------------------
  function initials(name) {
    var parts = (name || "?").trim().split(/\s+/);
    var s = parts[0].charAt(0);
    if (parts.length > 1) s += parts[parts.length - 1].charAt(0);
    return s.toUpperCase();
  }

  function el(tag, cls, html) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (html != null) e.innerHTML = html;
    return e;
  }

  function escapeHtml(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  // ---------------------------------------------------------------
  // Fuegos artificiales (canvas)
  // ---------------------------------------------------------------
  function Fireworks(canvas) {
    var ctx = canvas.getContext("2d");
    var particles = [];
    var running = false;
    var raf = null;
    var spawnTimer = null;
    var self = this;

    function resize() {
      canvas.width = canvas.offsetWidth;
      canvas.height = canvas.offsetHeight;
    }

    function burst(x, y) {
      var hue = Math.floor(Math.random() * 360);
      var count = 34 + Math.floor(Math.random() * 26);
      for (var i = 0; i < count; i++) {
        var angle = (Math.PI * 2 * i) / count;
        var speed = 1.5 + Math.random() * 4;
        particles.push({
          x: x, y: y,
          vx: Math.cos(angle) * speed,
          vy: Math.sin(angle) * speed,
          life: 1,
          decay: 0.008 + Math.random() * 0.012,
          color: "hsl(" + hue + "," + (70 + Math.random() * 30) + "%," + (55 + Math.random() * 15) + "%)"
        });
      }
    }

    function frame() {
      ctx.globalCompositeOperation = "source-over";
      ctx.fillStyle = "rgba(7,10,18,0.22)";
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      ctx.globalCompositeOperation = "lighter";
      for (var i = particles.length - 1; i >= 0; i--) {
        var p = particles[i];
        p.vx *= 0.99;
        p.vy = p.vy * 0.99 + 0.03; // gravedad
        p.x += p.vx;
        p.y += p.vy;
        p.life -= p.decay;
        if (p.life <= 0) { particles.splice(i, 1); continue; }
        ctx.globalAlpha = Math.max(p.life, 0);
        ctx.fillStyle = p.color;
        ctx.beginPath();
        ctx.arc(p.x, p.y, 2.4, 0, Math.PI * 2);
        ctx.fill();
      }
      ctx.globalAlpha = 1;
      if (running || particles.length) raf = requestAnimationFrame(frame);
    }

    this.start = function () {
      resize();
      running = true;
      frame();
      var scheduleBurst = function () {
        burst(canvas.width * (0.15 + Math.random() * 0.7),
              canvas.height * (0.12 + Math.random() * 0.4));
        spawnTimer = setTimeout(scheduleBurst, 450 + Math.random() * 650);
      };
      scheduleBurst();
      self._resize = resize;
      window.addEventListener("resize", resize);
    };

    this.stop = function () {
      running = false;
      if (spawnTimer) clearTimeout(spawnTimer);
      window.removeEventListener("resize", resize);
      // deja que las partículas restantes se apaguen solas
    };

    this.finale = function () {
      for (var k = 0; k < 5; k++) {
        (function (d) {
          setTimeout(function () {
            burst(canvas.width * (0.2 + Math.random() * 0.6),
                  canvas.height * (0.15 + Math.random() * 0.35));
          }, d * 180);
        })(k);
      }
    };
  }

  // ---------------------------------------------------------------
  // Ceremonia
  // ---------------------------------------------------------------
  var Ceremony = {
    overlay: null,
    fireworks: null,
    raceState: null,
    building: false,

    open: function () {
      if (this.building || this.overlay) return;
      this.building = true;
      var self = this;
      fetch(CFG.dataUrl, { headers: { "X-Requested-With": "fetch" } })
        .then(function (r) { return r.json(); })
        .then(function (data) {
          self.building = false;
          if (!data || (!data.ready && !data.preview)) {
            return; // aún no disponible para este usuario
          }
          if (!data.participants || !data.participants.length) {
            return;
          }
          self.render(data);
        })
        .catch(function () { self.building = false; });
    },

    close: function () {
      if (!this.overlay) return;
      var ov = this.overlay;
      this.overlay = null;
      if (this.fireworks) { this.fireworks.stop(); this.fireworks = null; }
      if (this.raceState && this.raceState.timer) clearTimeout(this.raceState.timer);
      this.raceState = null;
      document.body.classList.remove("cer-open");
      ov.classList.remove("cer-visible");
      setTimeout(function () { if (ov.parentNode) ov.parentNode.removeChild(ov); }, 350);
      try { sessionStorage.setItem(SEEN_KEY, "1"); } catch (e) {}
    },

    render: function (data) {
      var self = this;
      var ov = el("div", "cer-overlay");

      var canvas = el("canvas", "cer-canvas");
      ov.appendChild(canvas);

      if (data.preview) {
        ov.appendChild(el("div", "cer-preview-banner",
          "👁️ Previsualización (solo admin) — datos parciales"));
      }

      var closeBtn = el("button", "cer-close", "&times;");
      closeBtn.setAttribute("aria-label", "Cerrar");
      closeBtn.addEventListener("click", function () { self.close(); });
      ov.appendChild(closeBtn);

      var stageWrap = el("div", "cer-stage");
      stageWrap.appendChild(this.buildPodiumPanel(data));
      stageWrap.appendChild(this.buildRacePanel(data));
      ov.appendChild(stageWrap);

      document.body.appendChild(ov);
      document.body.classList.add("cer-open");
      this.overlay = ov;

      // Escape para cerrar
      this._onKey = function (e) { if (e.key === "Escape") self.close(); };
      document.addEventListener("keydown", this._onKey);

      requestAnimationFrame(function () { ov.classList.add("cer-visible"); });

      // Fuegos + entrada del podio
      this.fireworks = new Fireworks(canvas);
      this.fireworks.start();
      this.animatePodium(data);
    },

    // ---------------- Fase 1: Podio ----------------
    buildPodiumPanel: function (data) {
      var panel = el("div", "cer-panel cer-active");
      panel.dataset.panel = "podium";
      panel.appendChild(el("h1", "cer-title", "🏆 Clasificación final"));
      panel.appendChild(el("div", "cer-subtitle", SUBTITLE));

      var podium = el("div", "cer-podium");
      // Orden visual: 2º, 1º, 3º
      var order = [data.podium[1], data.podium[0], data.podium[2]];
      var spotClass = { 0: "cer-spot-2", 1: "cer-spot-1", 2: "cer-spot-3" };
      var medals = {};
      data.podium.forEach(function (p) {
        if (p) medals[p.position] = p;
      });

      order.forEach(function (p, idx) {
        if (!p) return;
        var spot = el("div", "cer-spot " + spotClass[idx]);
        spot.dataset.delay = idx === 1 ? 0 : (idx === 0 ? 350 : 700);

        var medalEmoji = p.position === 1 ? "🥇" : (p.position === 2 ? "🥈" : "🥉");
        spot.appendChild(el("div", "cer-medal", medalEmoji));
        spot.appendChild(el("div", "cer-avatar", initials(p.username)));
        var name = el("div", "cer-name",
          escapeHtml(p.username) + (p.isMe ? '<span class="cer-me-tag">tú</span>' : ""));
        spot.appendChild(name);
        var pts = el("div", "cer-pts");
        pts.dataset.target = p.points;
        pts.textContent = "0 pts";
        spot.appendChild(pts);
        spot.appendChild(el("div", "cer-block", p.position));
        podium.appendChild(spot);
      });
      panel.appendChild(podium);

      var controls = el("div", "cer-controls");
      var next = el("button", "cer-btn cer-btn-primary",
        "Ver evolución por etapas <i class=\"bi bi-arrow-right\"></i>");
      var self = this;
      next.addEventListener("click", function () { self.showRace(data); });
      controls.appendChild(next);
      panel.appendChild(controls);
      return panel;
    },

    animatePodium: function (data) {
      var self = this;
      var spots = this.overlay.querySelectorAll(".cer-spot");
      spots.forEach(function (spot) {
        var delay = parseInt(spot.dataset.delay, 10) || 0;
        setTimeout(function () {
          spot.classList.add("cer-in");
          if (self.fireworks) self.fireworks.finale();
          var pts = spot.querySelector(".cer-pts");
          if (pts) self.countUp(pts, parseInt(pts.dataset.target, 10) || 0);
        }, 500 + delay);
      });
    },

    countUp: function (node, target) {
      var start = performance.now();
      var dur = 900;
      function step(t) {
        var k = Math.min((t - start) / dur, 1);
        var val = Math.round(target * (1 - Math.pow(1 - k, 3)));
        node.textContent = val + " pts";
        if (k < 1) requestAnimationFrame(step);
      }
      requestAnimationFrame(step);
    },

    // ---------------- Fase 2: Bar race ----------------
    buildRacePanel: function (data) {
      var panel = el("div", "cer-panel");
      panel.dataset.panel = "race";
      panel.appendChild(el("h1", "cer-title", "📈 Cómo se sumaron los puntos"));

      var head = el("div", "cer-race-head");
      var pill = el("div", "cer-stage-pill", "Inicio");
      pill.dataset.role = "stagePill";
      head.appendChild(pill);
      panel.appendChild(head);

      var race = el("div", "cer-race");
      race.dataset.role = "race";
      panel.appendChild(race);

      var controls = el("div", "cer-controls");
      var replayPodium = el("button", "cer-btn",
        "<i class=\"bi bi-arrow-left\"></i> Volver al podio");
      var self = this;
      replayPodium.addEventListener("click", function () { self.showPodium(); });
      var replayRace = el("button", "cer-btn", "<i class=\"bi bi-arrow-repeat\"></i> Repetir");
      replayRace.addEventListener("click", function () { self.startRace(data); });
      var closeBtn = el("button", "cer-btn cer-btn-primary", "Cerrar");
      closeBtn.addEventListener("click", function () { self.close(); });
      controls.appendChild(replayPodium);
      controls.appendChild(replayRace);
      controls.appendChild(closeBtn);
      panel.appendChild(controls);
      return panel;
    },

    showPanel: function (which) {
      var panels = this.overlay.querySelectorAll(".cer-panel");
      panels.forEach(function (p) {
        p.classList.toggle("cer-active", p.dataset.panel === which);
      });
    },

    showPodium: function () {
      if (this.raceState && this.raceState.timer) clearTimeout(this.raceState.timer);
      this.showPanel("podium");
    },

    showRace: function (data) {
      this.showPanel("race");
      this.startRace(data);
    },

    startRace: function (data) {
      var self = this;
      var race = this.overlay.querySelector('[data-role="race"]');
      var pill = this.overlay.querySelector('[data-role="stagePill"]');
      if (this.raceState && this.raceState.timer) clearTimeout(this.raceState.timer);
      race.innerHTML = "";

      var participants = data.participants;
      var stages = data.stages;
      var rowH = 40;
      var maxTotal = 1;
      participants.forEach(function (p) { maxTotal = Math.max(maxTotal, p.total); });

      // Construir una fila por participante (orden inicial = alfabético/ranking).
      var rows = participants.map(function (p, i) {
        var row = el("div", "cer-row" + (p.isMe ? " cer-row-me" : ""));
        row.appendChild(el("span", "cer-row-rank", ""));
        row.appendChild(el("span", "cer-row-name", escapeHtml(p.username)));
        var barWrap = el("div", "cer-bar-wrap");
        barWrap.appendChild(el("div", "cer-bar"));
        row.appendChild(barWrap);
        row.appendChild(el("span", "cer-row-score", "0"));
        var gain = el("span", "cer-gain", "");
        row.appendChild(gain);
        race.appendChild(row);
        return { data: p, node: row, running: 0 };
      });
      race.style.height = (rows.length * rowH) + "px";

      function layout(sorted) {
        sorted.forEach(function (item, idx) {
          item.node.style.transform = "translateY(" + (idx * rowH) + "px)";
          item.node.querySelector(".cer-row-rank").textContent = (idx + 1) + ".";
          item.node.classList.remove("cer-row-1", "cer-row-2", "cer-row-3");
          if (idx < 3) item.node.classList.add("cer-row-" + (idx + 1));
        });
      }
      // Estado inicial (todos a 0, orden dado)
      layout(rows.slice());

      var stageIndex = 0;
      this.raceState = { timer: null };

      function tick() {
        if (stageIndex >= stages.length) {
          pill.textContent = "Final · " + stages.length + " etapas";
          self.showFinalGain(rows);
          return;
        }
        var stageNum = stages[stageIndex];
        pill.textContent = "Etapa " + stageNum;
        rows.forEach(function (item) {
          var gained = item.data.perStage[stageIndex] || 0;
          item.running += gained;
          var score = item.node.querySelector(".cer-row-score");
          score.textContent = item.running;
          var bar = item.node.querySelector(".cer-bar");
          bar.style.width = Math.max((item.running / maxTotal) * 100, 0) + "%";
          if (gained > 0) {
            var gain = item.node.querySelector(".cer-gain");
            gain.textContent = "+" + gained;
            gain.classList.remove("cer-pop");
            void gain.offsetWidth; // reflow para reiniciar animación
            gain.classList.add("cer-pop");
          }
        });
        var sorted = rows.slice().sort(function (a, b) {
          if (b.running !== a.running) return b.running - a.running;
          return a.data.username.localeCompare(b.data.username);
        });
        layout(sorted);
        stageIndex++;
        self.raceState.timer = setTimeout(tick, 1300);
      }

      // Arranque tras un breve respiro
      this.raceState.timer = setTimeout(tick, 600);
    },

    showFinalGain: function (rows) {
      if (this.fireworks) this.fireworks.finale();
    }
  };

  // RaceCeremony es el nombre nuevo; TDFCeremony se mantiene para no romper
  // las plantillas archivadas del Tour.
  window.RaceCeremony = Ceremony;
  window.TDFCeremony = Ceremony;

  // ---------------------------------------------------------------
  // Auto-apertura + botón flotante
  // ---------------------------------------------------------------
  document.addEventListener("DOMContentLoaded", function () {
    if (!CFG.dataUrl) return;

    // Botón flotante permanente (solo cuando la ceremonia ya está disponible).
    if (CFG.ready) {
      var fab = el("button", "cer-fab",
        '<span class="cer-fab-emoji">🏆</span> Ver ceremonia');
      fab.addEventListener("click", function () { Ceremony.open(); });
      document.body.appendChild(fab);

      // Auto-apertura una vez por sesión de navegador.
      var seen = false;
      try { seen = sessionStorage.getItem(SEEN_KEY) === "1"; } catch (e) {}
      if (!seen) {
        setTimeout(function () { Ceremony.open(); }, 600);
      }
    }
  });
})();

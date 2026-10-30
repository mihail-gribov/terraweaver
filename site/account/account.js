/* The account page: sign-in screen, then four sections over the JSON API of site/auth/app.py. */
(function () {
  "use strict";
  var state = { me: null, fresh: null };           // fresh: the key made in this visit, kept in memory only
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var esc = function (t) { return String(t).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); };
  var day = function (t) { return t ? new Date(t * 1000).toISOString().slice(0, 10) : "-"; };

  function api(method, path, body) {
    return fetch("/auth/api" + path, {
      method: method, credentials: "same-origin",
      headers: body ? { "Content-Type": "application/json" } : {}, body: body ? JSON.stringify(body) : undefined
    }).then(function (r) {
      return r.json().catch(function () { return {}; }).then(function (d) {
        if (r.status === 401) { state.me = null; show(); throw new Error("signed out"); }
        if (!r.ok) throw new Error(d.error || "Something went wrong");
        return d;
      });
    });
  }

  function toast(text) {
    var t = $("#toast"); t.textContent = text; t.hidden = false;
    clearTimeout(toast.t); toast.t = setTimeout(function () { t.hidden = true; }, 2200);
  }
  function copy(text) {
    var done = function () { toast("Copied"); };
    if (navigator.clipboard) navigator.clipboard.writeText(text).then(done, function () { toast("Select and copy by hand"); });
    else toast("Select and copy by hand");
  }

  function modal(html, onMount) {
    var m = $("#modal"); $("#modalCard").innerHTML = html; m.hidden = false;
    m.onclick = function (e) { if (e.target === m) close(); };
    function close() { m.hidden = true; $("#modalCard").innerHTML = ""; }
    if (onMount) onMount(close);
    return close;
  }

  /* ---- sections ---- */
  var views = {
    overview: function (root) {
      var me = state.me, n = me.keys.length;
      root.innerHTML =
        '<h1>Overview</h1><p class="lead">Signed in as <strong>' + esc(me.email) + '</strong>.</p>' +
        '<div class="stats">' +
        '<div class="stat"><b>' + n + ' / ' + me.max_keys + '</b><span>active keys</span></div>' +
        '<div class="stat"><b>' + (me.created ? day(me.created) : "today") + '</b><span>account made</span></div>' +
        '<div class="stat"><b><span class="badge badge-ok">online</span></b><span>demo memory</span></div></div>' +
        '<div class="card"><div class="card-h"><h2>Endpoint</h2></div>' +
        '<p class="dim" style="margin-top:0">Every MCP client uses this address and one of your keys as the bearer token.</p>' +
        '<pre class="code"><button class="btn btn-sm copy" data-copy="' + esc(me.endpoint) + '">Copy</button>' + esc(me.endpoint) + '</pre></div>' +
        (n ? '' : '<div class="card"><div class="card-h"><h2>Start here</h2></div><p style="margin-top:0">You have no key yet.</p>' +
          '<a class="btn btn-primary" href="#keys">Make a key</a></div>') +
        '<div class="note warn-note"><strong>Evaluation demo.</strong> One shared memory: everything typed to it is visible to every key holder and may be erased. ' +
        'Use an invented person. For real use, run TerraWeaver on your own machine; no key is needed there.</div>';
    },

    keys: function (root) {
      var me = state.me, full = me.keys.length >= me.max_keys;
      var rows = me.keys.map(function (k) {
        return '<tr><td><strong>' + esc(k.name) + '</strong></td><td class="mono">' + esc(k.prefix) + '…</td><td>' + day(k.created) +
          '</td><td class="act"><button class="btn btn-sm btn-danger" data-revoke="' + esc(k.id) + '" data-name="' + esc(k.name) + '">Revoke</button></td></tr>';
      }).join("");
      root.innerHTML =
        '<h1>API keys</h1><p class="lead">A key is the bearer token of the hosted demo memory. It is shown once, when you make it.</p>' +
        '<div class="card"><div class="card-h"><h2>Make a key</h2></div><form id="mk" class="row">' +
        '<div class="field"><label for="kn">Name</label><input id="kn" class="inp" maxlength="40" placeholder="e.g. Claude Code on my laptop"' + (full ? " disabled" : "") + '></div>' +
        '<button class="btn btn-primary" type="submit"' + (full ? " disabled" : "") + '>Make key</button></form>' +
        (full ? '<p class="err">You have ' + me.max_keys + ' keys, the most there can be. Revoke one first.</p>' : '') + '<p class="err" id="mkerr"></p></div>' +
        '<div class="card"><div class="card-h"><h2>Your keys</h2></div>' +
        (me.keys.length ? '<table><thead><tr><th>Name</th><th>Key</th><th>Made</th><th></th></tr></thead><tbody>' + rows + '</tbody></table>'
          : '<div class="empty">No keys yet.</div>') + '</div>';
      $("#mk").onsubmit = function (e) {
        e.preventDefault();
        var btn = $("#mk button"); btn.disabled = true;
        api("POST", "/keys", { name: $("#kn").value }).then(function (d) {
          state.fresh = d.key; return reload().then(function () {
            modal('<h2>Your new key</h2><p class="dim" style="margin:0">Copy it now. It is not kept anywhere in clear, and cannot be shown again.</p>' +
              '<div class="keybox">' + esc(d.key) + '</div><div class="actions"><button class="btn" id="mc">Copy</button>' +
              '<button class="btn btn-primary" id="md">Done</button></div>', function (close) {
              $("#mc").onclick = function () { copy(d.key); }; $("#md").onclick = close;
            });
          });
        }).catch(function (er) { $("#mkerr").textContent = er.message; btn.disabled = false; });
      };
      root.onclick = function (e) {
        var b = e.target.closest("[data-revoke]"); if (!b) return;
        modal('<h2>Revoke “' + esc(b.dataset.name) + '”?</h2><p class="dim" style="margin:0">Anything that uses this key stops working at once.</p>' +
          '<div class="actions"><button class="btn" id="rn">Cancel</button><button class="btn btn-danger" id="ry">Revoke</button></div>', function (close) {
          $("#rn").onclick = close;
          $("#ry").onclick = function () {
            api("DELETE", "/keys/" + b.dataset.revoke).then(function () { close(); return reload(); }).then(function () { toast("Key revoked"); })
              .catch(function (er) { close(); toast(er.message); });
          };
        });
      };
    },

    connect: function (root) {
      var key = state.fresh || "tw_…your key…", me = state.me;
      var snippets = {
        "Claude Code": 'git clone https://github.com/mihail-gribov/terraweaver && cd terraweaver\n' +
          'export PERSONAL_MEMORY_URL=https://terraweaver.life\nexport PERSONAL_MEMORY_TOKEN=' + key + '\nadapters/claude_code/claude-personal',
        "Other MCP client": 'URL:     ' + me.endpoint + '\nHeader:  Authorization: Bearer ' + key,
        "Check it": 'curl -s -X POST ' + me.endpoint.replace(/\/mcp$/, "") + '/say \\\n  -H "Authorization: Bearer ' + key + '" \\\n  -H "Content-Type: application/json" \\\n  -d \'{"messages":[{"role":"user","text":"My cat is called Pepper."}]}\''
      };
      var names = Object.keys(snippets), cur = names[0];
      function draw() {
        $("#snip").innerHTML = '<button class="btn btn-sm copy" id="cp">Copy</button>' + esc(snippets[cur]);
        $("#cp").onclick = function () { copy(snippets[cur]); };
        document.querySelectorAll(".tabs button").forEach(function (b) { b.classList.toggle("on", b.textContent === cur); });
      }
      root.innerHTML = '<h1>Connect</h1><p class="lead">Point an agent at the demo memory.' +
        (state.fresh ? ' Your new key is already in the snippets below.' : ' Make a key under <a href="#keys">API keys</a> and paste it in place of the placeholder.') + '</p>' +
        '<div class="card"><div class="tabs">' + names.map(function (n) { return '<button type="button">' + esc(n) + '</button>'; }).join("") +
        '</div><pre class="code" id="snip"></pre>' +
        '<p class="small dim" style="margin-bottom:0">With the Claude Code plugin the hooks call <code>say</code> by themselves; any other client calls <code>say</code> with what was said and <code>ask</code> with what it needs. A first <code>ask</code> may wait while the memory reads.</p></div>' +
        '<div class="note warn-note">Shared demo, for evaluation: invented facts only. On your own machine the memory needs no key.</div>';
      document.querySelectorAll(".tabs button").forEach(function (b) { b.onclick = function () { cur = b.textContent; draw(); }; });
      draw();
    },

    profile: function (root) {
      var me = state.me;
      root.innerHTML = '<h1>Profile</h1><p class="lead">Your account is your Google account; nothing else is asked.</p>' +
        '<div class="card"><div class="card-h"><h2>Account</h2></div><table><tbody>' +
        '<tr><th>Email</th><td>' + esc(me.email) + '</td></tr>' +
        '<tr><th>Sign-in</th><td>Google</td></tr><tr><th>Made</th><td>' + (me.created ? day(me.created) : "with your first key") + '</td></tr></tbody></table>' +
        '<p class="small dim">We keep your email, the Google account identifier, and a one-way hash of each key. See the <a href="/privacy.html">privacy notice</a>.</p>' +
        '<button class="btn" id="out">Sign out</button></div>' +
        '<div class="card danger-zone"><div class="card-h"><h2>Delete account</h2></div>' +
        '<p class="dim" style="margin-top:0">Removes your account and every key at once. What was said to the shared demo memory stays in its journal until it is erased; ask through the contacts on the site to have it removed sooner.</p>' +
        '<button class="btn btn-danger" id="del">Delete my account</button></div>';
      $("#out").onclick = function () { api("POST", "/logout").then(function () { state.me = null; show(); }).catch(function () {}); };
      $("#del").onclick = function () {
        modal('<h2>Delete your account?</h2><p class="dim" style="margin:0">This removes ' + esc(me.email) + ' and all ' + me.keys.length + ' key(s). It cannot be undone.</p>' +
          '<div class="actions"><button class="btn" id="dn">Cancel</button><button class="btn btn-danger" id="dy">Delete</button></div>', function (close) {
          $("#dn").onclick = close;
          $("#dy").onclick = function () { api("DELETE", "/account").then(function () { close(); state.me = null; show(); }).catch(function (e) { close(); toast(e.message); }); };
        });
      };
    }
  };

  function route() {
    if (!state.me) return;
    var name = (location.hash || "#overview").slice(1);
    if (!views[name]) name = "overview";
    document.querySelectorAll("#menu a").forEach(function (a) { a.classList.toggle("active", a.dataset.view === name); });
    $("#side").classList.remove("open"); $("#burger").setAttribute("aria-expanded", "false");
    var root = $("#view"); root.onclick = null; views[name](root);
    document.title = name[0].toUpperCase() + name.slice(1) + " · TerraWeaver account";
  }

  function show() {
    $("#auth").hidden = !!state.me; $("#app").hidden = !state.me;
    if (state.me) { $("#who").textContent = state.me.email; route(); }
  }
  function reload() { return api("GET", "/me").then(function (d) { state.me = d; route(); }); }

  $("#burger").onclick = function () { var o = $("#side").classList.toggle("open"); this.setAttribute("aria-expanded", String(o)); };
  document.addEventListener("click", function (e) { var b = e.target.closest("[data-copy]"); if (b) copy(b.dataset.copy); });
  window.addEventListener("hashchange", route);
  document.addEventListener("keydown", function (e) { if (e.key === "Escape") { $("#modal").hidden = true; } });

  fetch("/auth/api/me", { credentials: "same-origin" }).then(function (r) { return r.ok ? r.json() : null; })
    .catch(function () { return null; }).then(function (d) { state.me = d; show(); });
})();

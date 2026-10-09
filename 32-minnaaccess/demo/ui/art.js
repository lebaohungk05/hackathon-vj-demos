const ICON = {
  listen: `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 9.5h3.2L12 5.5v13l-4.8-4H4z" fill="currentColor"/><path d="M15.2 8.6a4.6 4.6 0 0 1 0 6.8M17.8 6a8.2 8.2 0 0 1 0 12" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>`,
  navigate: `<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="2.5" y="6" width="19" height="12" rx="2.2" fill="none" stroke="currentColor" stroke-width="1.7"/><path d="M6 10h1.6M9.2 10h1.6M12.4 10h1.6M15.6 10H18M6 14h8.5M16.5 12.6l1.6 1.4-1.6 1.4" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>`,
  restart: `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M19 12a7 7 0 1 1-2.05-4.95" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round"/><path d="M17.6 3.6v4.2h-4.2" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"/></svg>`,
};

function stepStrip() {
  const steps = [["listen", "Listen", "screen reader"], ["navigate", "Navigate", "keyboard only"], ["restart", "Restart", "from step 1"]];
  return `<ol class="steps3">${steps.map(([k, label, sub]) => `<li class="s-${k}"><span class="si">${ICON[k]}</span><span class="sl"><b>${th(label)}</b><small>${th(sub)}</small></span></li>`).join("")}</ol>`;
}

function blossom(x, y, r, rot) {
  return `<use href="#ha-bl" transform="translate(${x} ${y}) rotate(${rot || 0}) scale(${r})"/>`;
}

function heroSvg(variant) {
  const v = variant || "listen";
  const screen = v === "done"
    ? `<circle cx="490" cy="318" r="40" fill="#178a6a"/><path d="M470 318l14 14 26-28" fill="none" stroke="#fff" stroke-width="9" stroke-linecap="round" stroke-linejoin="round"/>`
    : v === "wait"
      ? `<circle class="ha-spin" cx="490" cy="318" r="34" fill="none" stroke="#c3392f" stroke-width="7" stroke-dasharray="150 70" stroke-linecap="round"/>`
      : `<g fill="#e9e1d1"><rect x="392" y="262" width="62" height="5" rx="2.5"/><rect x="392" y="304" width="74" height="5" rx="2.5"/><rect x="392" y="346" width="54" height="5" rx="2.5"/></g>
        <g fill="#fff" stroke="#c9bfab" stroke-width="1.6"><rect x="392" y="272" width="196" height="22" rx="5"/><rect x="392" y="314" width="196" height="22" rx="5"/><rect x="392" y="356" width="196" height="22" rx="5"/></g>
        <rect x="392" y="388" width="62" height="16" rx="4" fill="#2563eb"/>
        <rect class="ha-focus" x="388" y="268" width="204" height="30" rx="8" fill="none" stroke="#c3392f" stroke-width="3.2"/>
        <g class="ha-tab" fill="none" stroke="#b8913f" stroke-width="2" stroke-dasharray="3 5" stroke-linecap="round"><path d="M596 283c22 4 22 38 0 42"/><path d="M596 325c22 4 22 38 0 42"/><path d="M596 367c18 4 4 30-130 29"/></g>
        <g fill="#141036"><circle cx="618" cy="304" r="9"/><circle cx="618" cy="346" r="9"/></g>
        <g fill="none" stroke="#f6f1e4" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M613 304h9M619 300.5l3.5 3.5-3.5 3.5"/><path d="M613 346h9M619 342.5l3.5 3.5-3.5 3.5"/></g>`;
  return `<svg class="hero-art hero-${v}" viewBox="0 0 800 500" preserveAspectRatio="xMidYMid meet" aria-hidden="true" focusable="false">
  <defs>
    <radialGradient id="ha-sun" cx=".45" cy=".42" r=".6"><stop offset="0" stop-color="#d9544a"/><stop offset=".75" stop-color="#e8857b"/><stop offset="1" stop-color="#f3b3ab"/></radialGradient>
    <linearGradient id="ha-mt" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#6c7ea3"/><stop offset="1" stop-color="#d7deea"/></linearGradient>
    <linearGradient id="ha-far" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#9aa8c2"/><stop offset="1" stop-color="#e6eaf1"/></linearGradient>
    <linearGradient id="ha-body" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#262c52"/><stop offset="1" stop-color="#121633"/></linearGradient>
    <linearGradient id="ha-water" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#dfe5ee"/><stop offset="1" stop-color="#f9f6ef" stop-opacity="0"/></linearGradient>
    <pattern id="ha-sg" width="40" height="20" patternUnits="userSpaceOnUse"><image href="assets/seigaiha.svg" width="40" height="20"/></pattern>
    <radialGradient id="ha-fade" cx=".5" cy=".55" r=".55"><stop offset=".55" stop-color="#fff"/><stop offset="1" stop-color="#000"/></radialGradient>
    <mask id="ha-soft"><rect width="800" height="500" fill="url(#ha-fade)"/></mask>
    <g id="ha-bl"><g fill="#f6c3cc" stroke="#e79aa8" stroke-width=".6"><ellipse cx="0" cy="-6" rx="4.2" ry="6"/><ellipse cx="0" cy="-6" rx="4.2" ry="6" transform="rotate(72)"/><ellipse cx="0" cy="-6" rx="4.2" ry="6" transform="rotate(144)"/><ellipse cx="0" cy="-6" rx="4.2" ry="6" transform="rotate(216)"/><ellipse cx="0" cy="-6" rx="4.2" ry="6" transform="rotate(288)"/></g><circle r="2.2" fill="#c9506a"/></g>
  </defs>
  <g mask="url(#ha-soft)">
    <rect width="800" height="500" fill="url(#ha-sg)" opacity=".45"/>
    <rect x="0" y="410" width="800" height="90" fill="url(#ha-water)"/>
    <path d="M0 412h800" stroke="#c8d0de" stroke-width="1.5"/>
    <path d="M20 404h190" stroke="#c8d0de" stroke-width="1"/>
  </g>
  <circle cx="640" cy="112" r="80" fill="url(#ha-sun)" opacity=".88"/>
  <g fill="none" stroke="#7a4a3a" stroke-linecap="round"><path d="M806 18C740 40 690 52 600 96" stroke-width="7"/><path d="M700 52c-20-22-30-34-58-40" stroke-width="3.5"/><path d="M640 82c-6 18-4 30 6 46" stroke-width="3"/><path d="M760 34c10 20 8 40-6 58" stroke-width="3"/></g>
  <g>${blossom(604, 94, 1.5, 10)}${blossom(632, 76, 1.2, 40)}${blossom(646, 16, 1.3, 0)}${blossom(668, 36, 1.6, 22)}${blossom(646, 128, 1.3, 60)}${blossom(722, 50, 1.4, 12)}${blossom(752, 90, 1.5, 30)}${blossom(780, 26, 1.2, 50)}${blossom(700, 68, 1.1, 5)}</g>
  <path d="M590 412L688 312Q704 298 720 312L812 412Z" fill="url(#ha-mt)" opacity=".85"/>
  <path d="M664 336L688 312Q704 298 720 312L744 336L732 331L722 341L711 330L700 343L689 330L678 340Z" fill="#fff"/>
  <g fill="#c3392f"><rect x="610" y="356" width="5" height="56"/><rect x="638" y="356" width="5" height="56"/><path d="M598 348q28 -8 56 0v6q-28 -6 -56 0z"/><rect x="604" y="362" width="45" height="4"/></g>
  <g fill="#3b4566"><rect x="768" y="318" width="4" height="14"/><path d="M752 336h36l-8-6h-20z"/><rect x="758" y="336" width="24" height="12"/><path d="M748 352h44l-8-6h-28z"/><rect x="756" y="352" width="28" height="13"/><path d="M744 369h52l-9-6h-34z"/><rect x="754" y="369" width="32" height="43"/></g>
  <g fill="url(#ha-far)" opacity=".8"><rect x="6" y="362" width="16" height="50"/><rect x="26" y="348" width="13" height="64"/><rect x="43" y="372" width="20" height="40"/><rect x="150" y="366" width="14" height="46"/><rect x="167" y="380" width="18" height="32"/></g>
  <g fill="#4a5578"><rect x="96" y="374" width="7" height="38"/><rect x="84" y="359" width="31" height="15" rx="1"/><path d="M77 361q22 -16 45 0l-6 1q-17 -11 -33 0z"/><path d="M93 348l7-6 7 6z"/><path d="M74 412q26 -6 52 0" fill="none" stroke="#9aa8c2" stroke-width="2"/></g>
  <g fill="none" stroke="#5f6c8f" stroke-width="2"><path d="M8 404h196"/><path d="M8 404q24 -26 48 0q25 -26 50 0q24 -26 49 0q24 -26 49 0"/><path d="M20 393v11M32 386v18M44 393v11M69 393v11M81 386v18M93 393v11M118 393v11M130 386v18M142 393v11M167 393v11M179 386v18M191 393v11" stroke-width="1.3"/></g>
  <g transform="translate(70 44) scale(.84)">
    <path d="M120 440h540" stroke="#d8ccb4" stroke-width="10" stroke-linecap="round"/>
    <path d="M352 430h292l18 10H334z" fill="#2b2f52"/>
    <rect x="364" y="222" width="252" height="208" rx="12" fill="#141036"/>
    <rect x="376" y="234" width="228" height="184" rx="4" fill="#fffdf9"/>
    <rect x="376" y="234" width="228" height="18" fill="#c3392f"/>
    ${screen}
    <g class="ha-waves" fill="none" stroke="#2a6496" stroke-linecap="round"><path class="w1" d="M356 268q-10 18 0 36" stroke-width="3.4"/><path class="w2" d="M346 256q-16 30 0 60" stroke-width="3"/><path class="w3" d="M336 244q-22 42 0 84" stroke-width="2.6"/></g>
    <path d="M150 446c4-56 26-96 66-112 22-9 50-9 72 0 38 16 58 56 62 112z" fill="url(#ha-body)"/>
    <path d="M300 352c26 14 50 38 66 70" fill="none" stroke="#1b2042" stroke-width="26" stroke-linecap="round"/>
    <ellipse cx="380" cy="430" rx="16" ry="8" fill="#e8c4a6"/>
    <rect x="236" y="300" width="30" height="40" rx="10" fill="#d9b394"/>
    <circle cx="252" cy="268" r="44" fill="#1a1d38"/>
    <path d="M276 250c14 6 22 22 20 40-8 16-26 22-40 16" fill="#e2bd9e"/>
    <path d="M206 266c-4-38 22-64 54-62 30 2 50 26 46 54-12-18-32-26-54-24-20 2-34 14-46 32z" fill="#0f1129"/>
    <path d="M212 250c2-44 82-58 92 0" fill="none" stroke="#2c335e" stroke-width="9" stroke-linecap="round"/>
    <ellipse cx="296" cy="270" rx="13" ry="21" fill="#2c335e"/><ellipse cx="298" cy="270" rx="6" ry="13" fill="#454d7c"/>
  </g>
  <image href="assets/lotus.svg" x="636" y="396" width="140" height="108"/>
  <g class="ha-petals" fill="#f2b6c1"><ellipse class="p1" cx="560" cy="150" rx="4" ry="6.5"/><ellipse class="p2" cx="700" cy="170" rx="3.5" ry="5.5"/><ellipse class="p3" cx="520" cy="80" rx="3" ry="5"/><ellipse class="p4" cx="770" cy="200" rx="3.5" ry="6"/></g>
</svg>`;
}

function heroFill(variant, withStrip) {
  return `<div class="hero-fill">${heroSvg(variant)}</div>${withStrip ? stepStrip() : ""}`;
}

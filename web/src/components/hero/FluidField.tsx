import { useEffect, useRef } from "react";

/** Where the pointer is over the hero, 0..1 from the bottom-left (WebGL's origin). */
export type PointerRef = { current: { x: number; y: number } };

const VERTEX = `attribute vec2 p; void main() { gl_Position = vec4(p, 0.0, 1.0); }`;

// Blue ink diffusing in water: domain-warped noise, pulled gently toward the pointer.
const FRAGMENT = `
precision mediump float;
uniform vec2 u_res;
uniform float u_time;
uniform vec2 u_pointer;
uniform vec3 u_bg;
uniform vec3 u_ink;
uniform float u_strength;

float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float noise(vec2 p) {
  vec2 i = floor(p), f = fract(p);
  vec2 u = f * f * (3.0 - 2.0 * f);
  return mix(mix(hash(i), hash(i + vec2(1.0, 0.0)), u.x), mix(hash(i + vec2(0.0, 1.0)), hash(i + vec2(1.0, 1.0)), u.x), u.y);
}
float fbm(vec2 p) {
  float v = 0.0, a = 0.5;
  for (int i = 0; i < 5; i++) { v += a * noise(p); p = p * 2.03 + vec2(1.7, 9.2); a *= 0.5; }
  return v;
}
void main() {
  vec2 aspect = vec2(u_res.x / u_res.y, 1.0);
  vec2 p = gl_FragCoord.xy / u_res * aspect * 2.2;
  vec2 d = p - u_pointer * aspect * 2.2;
  float pull = exp(-dot(d, d) * 1.4);
  p -= d * pull * 0.35;
  float t = u_time * 0.035;
  vec2 q = vec2(fbm(p + t), fbm(p + vec2(5.2, 1.3) - t));
  vec2 r = vec2(fbm(p + 3.0 * q + vec2(1.7, 9.2) + t * 1.3), fbm(p + 3.0 * q + vec2(8.3, 2.8) - t));
  float ink = smoothstep(0.42, 0.95, fbm(p + 3.0 * r)) * (0.55 + 0.45 * length(q));
  ink = clamp(ink + pull * 0.12, 0.0, 1.0);
  gl_FragColor = vec4(mix(u_bg, u_ink, ink * u_strength), 1.0);
}`;

function rgb(value: string): [number, number, number] {
  const hex = value.trim().replace("#", "");
  const n = parseInt(hex.length === 3 ? hex.replace(/./g, "$&$&") : hex.slice(0, 6), 16);
  return [((n >> 16) & 255) / 255, ((n >> 8) & 255) / 255, (n & 255) / 255];
}

/** A full-bleed WebGL canvas behind the hero. Draws nothing without WebGL;
 *  one still frame under reduced motion; pauses offscreen or in a hidden tab. */
export function FluidField({ pointer, className = "" }: { pointer: PointerRef; className?: string }) {
  const canvas = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const el = canvas.current;
    if (!el || typeof window.WebGLRenderingContext === "undefined") return;
    const gl = el.getContext("webgl", { antialias: false, alpha: false, powerPreference: "low-power" });
    if (!gl) return;

    const shader = (type: number, src: string) => {
      const s = gl.createShader(type)!;
      gl.shaderSource(s, src);
      gl.compileShader(s);
      return s;
    };
    const program = gl.createProgram()!;
    gl.attachShader(program, shader(gl.VERTEX_SHADER, VERTEX));
    gl.attachShader(program, shader(gl.FRAGMENT_SHADER, FRAGMENT));
    gl.linkProgram(program);
    if (!gl.getProgramParameter(program, gl.LINK_STATUS)) return;
    gl.useProgram(program);
    gl.bindBuffer(gl.ARRAY_BUFFER, gl.createBuffer());
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW);
    const loc = gl.getAttribLocation(program, "p");
    gl.enableVertexAttribArray(loc);
    gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0);
    const u = (name: string) => gl.getUniformLocation(program, name);
    const [uRes, uTime, uPointer, uBg, uInk, uStrength] =
      ["u_res", "u_time", "u_pointer", "u_bg", "u_ink", "u_strength"].map(u);

    // Colours follow the theme tokens, re-read when the theme changes.
    const applyTheme = () => {
      const css = getComputedStyle(document.documentElement);
      const dark = document.documentElement.dataset.theme === "dark";
      gl.uniform3fv(uBg, rgb(css.getPropertyValue("--bg") || "#f6f6f3"));
      gl.uniform3fv(uInk, rgb(css.getPropertyValue("--pencil") || "#2f62d8"));
      gl.uniform1f(uStrength, dark ? 0.3 : 0.16);
    };

    // Half resolution is plenty for soft ink, and cheap.
    const resize = () => {
      const scale = Math.min(window.devicePixelRatio || 1, 2) * 0.5;
      el.width = Math.max(1, Math.round(el.clientWidth * scale));
      el.height = Math.max(1, Math.round(el.clientHeight * scale));
      gl.viewport(0, 0, el.width, el.height);
      gl.uniform2f(uRes, el.width, el.height);
    };

    const still = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;
    const smooth = { x: pointer.current.x, y: pointer.current.y };
    const start = performance.now();
    let frame = 0;
    let visible = true;

    const draw = (now: number) => {
      smooth.x += (pointer.current.x - smooth.x) * 0.04;
      smooth.y += (pointer.current.y - smooth.y) * 0.04;
      gl.uniform1f(uTime, still ? 24 : (now - start) / 1000 + 24);
      gl.uniform2f(uPointer, smooth.x, smooth.y);
      gl.drawArrays(gl.TRIANGLES, 0, 3);
    };
    const loop = (now: number) => {
      draw(now);
      frame = requestAnimationFrame(loop);
    };
    const run = () => {
      cancelAnimationFrame(frame);
      if (still) draw(start);
      else if (visible && !document.hidden) frame = requestAnimationFrame(loop);
    };

    applyTheme();
    resize();
    run();

    const sizeObserver = new ResizeObserver(() => { resize(); if (still) draw(start); });
    sizeObserver.observe(el);
    const themeObserver = new MutationObserver(() => { applyTheme(); if (still) draw(start); });
    themeObserver.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
    const viewObserver = new IntersectionObserver(([entry]) => { visible = entry.isIntersecting; run(); });
    viewObserver.observe(el);
    document.addEventListener("visibilitychange", run);

    return () => {
      cancelAnimationFrame(frame);
      sizeObserver.disconnect();
      themeObserver.disconnect();
      viewObserver.disconnect();
      document.removeEventListener("visibilitychange", run);
      gl.getExtension("WEBGL_lose_context")?.loseContext();
    };
  }, [pointer]);

  return <canvas ref={canvas} aria-hidden="true" className={`pointer-events-none block size-full ${className}`} />;
}

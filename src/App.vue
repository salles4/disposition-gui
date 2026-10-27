<template>
  <router-view />
</template>

<style>
/* GLOBAL CSS FOR ALL TERMINALS */
@font-face {
  font-family: 'LocalPlateFont';
  src: url('./assets/plate_font.ttf') format('truetype');
  font-weight: normal; font-style: normal;
}

body { margin: 0; padding: 0; background-color: #1a1a1a; font-family: 'Segoe UI', sans-serif; color: #e0e0e0; overflow: hidden; display: flex; height: 100vh; width: 100vw; }
#app { width: 100%; height: 100%; display: flex; }

/* The layout shared by Entry and Exit views */
.terminal-layout { display: flex; width: 100%; height: 100%; }
.viewport { flex: 1; background-color: #ffffff; position: relative; overflow: hidden; box-shadow: inset 0 0 20px rgba(0,0,0,0.1); }
.controls-panel { width: 340px; background-color: #111111; padding: 20px; border-left: 1px solid #2d2d2d; box-sizing: border-box; display: flex; flex-direction: column; gap: 15px; z-index: 10; }

/* UI Elements */
.panel-title { font-size: 1.1rem; font-weight: 600; color: #fff; border-bottom: 2px solid #007bff; padding-bottom: 8px; margin-bottom: 5px; display: flex; justify-content: space-between;}
.meta-box { background-color: #1e1e1e; padding: 10px; border-radius: 6px; border: 1px solid #2b2b2b; }
.meta-label { font-size: 0.75rem; color: #888; text-transform: uppercase; margin-bottom: 4px; }
.meta-value { font-size: 1.2rem; font-weight: bold; font-family: 'LocalPlateFont', monospace; color: #00ff66; }

/* Animations & Vehicles */
.car-wrapper { position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%) scale(0); opacity: 0; width: 600px; height: auto; pointer-events: none; }
.vehicle-img { width: 100%; height: auto; display: block; }
.plate-text { position: absolute; left: 50%; transform: translateX(-50%); color: #111111; font-family: 'LocalPlateFont', monospace; font-weight: 500; display: flex; justify-content: center; align-items: center; text-align: center; text-transform: uppercase; box-sizing: border-box; white-space: nowrap; overflow: hidden; }
.plate-inner-text { display: inline-block; transform-origin: center; white-space: nowrap; transition: transform 0.1s ease-out; }

.plate-car-front { top: 64%; width: 18%; height: 7.5%; font-size: 1.25rem; letter-spacing: -0.5px; }
.plate-car-back { top: 42.5%; width: 18%; height: 7.5%; font-size: 1.25rem; letter-spacing: -0.5px; }
.plate-motor-front { left: 51.14% !important; top: 68.5%; width: 10%; height: 6%; font-size: 0.8rem; letter-spacing: -0.5px; }
.plate-motor-back { left: 51.14% !important; top: 68.5%; width: 10%; height: 6%; font-size: 0.8rem; letter-spacing: -0.5px; }

/* 🚗 CAR FRONT ANIMATION (Drives Towards Camera) */
@keyframes carFrontSequence { 
  0%   { opacity: 1; transform: translate(-50%, -80%) scale(0.5); } 
  15%  { opacity: 1; transform: translate(-50%, -80%) scale(2.1); } /* Drives in */
  70%  { opacity: 1; transform: translate(-50%, -50%) scale(2.6); } /* STOPS to be scanned for 4 seconds */
  90%  { opacity: 1; transform: translate(-50%, -50%) scale(2.8); } /* STOPS to be scanned for 4 seconds */
  99%  { opacity: 1; transform: translate(-50%, -50%) scale(10.0); } /* Drives past camera */
  100% { opacity: 0; transform: translate(-50%, -50%) scale(10.0); } 
}
.run-car-front { animation: carFrontSequence 12s linear forwards; }

/* 🚗 CAR BACK ANIMATION (Drives Away From Camera) */
@keyframes carBackSequence { 
  0%   { opacity: 0; transform: translate(-50%, -80%) scale(10.0); } /* Starts right up against the lens */
  1%   { opacity: 1; transform: translate(-50%, -80%) scale(10.0); } 
  15%  { opacity: 1; transform: translate(-50%, -80%) scale(2.8); } /* Moves to scan position */
  70%  { opacity: 1; transform: translate(-50%, -50%) scale(2.6); } /* STOPS to be scanned */
  90%  { opacity: 1; transform: translate(-50%, -50%) scale(2.1); } /* STOPS to be scanned */
  99%  { opacity: 1; transform: translate(-50%, -50%) scale(0.5); } /* Drives far away */
  100% { opacity: 0; transform: translate(-50%, -50%) scale(0.5); } 
}
.run-car-back { animation: carBackSequence 12s linear forwards; }

/* 🏍️ MOTORCYCLE FRONT ANIMATION (Drives Towards Camera) */
@keyframes motorFrontSequence { 
  0%   { opacity: 1; transform: translate(-50%, -130%) scale(0.2); } /* Starts far away */
  15%  { opacity: 1; transform: translate(-50%, -80%) scale(3.7); } /* Drives in */
  70%  { opacity: 1; transform: translate(-50%, -140%) scale(3.7); } /* STOPS to be scanned */
  90%  { opacity: 1; transform: translate(-50%, -130%) scale(5.8); } /* STOPS to be scanned */
  99%  { opacity: 1; transform: translate(-50%, -50%) scale(10.0); } /* Drives past camera */
  100% { opacity: 0; transform: translate(-50%, -50%) scale(10.0); } 
}
.run-motor-front { animation: motorFrontSequence 12s linear forwards; }

/* 🏍️ MOTORCYCLE BACK ANIMATION (Drives Away From Camera) */
@keyframes motorBackSequence { 
  0%   { opacity: 0; transform: translate(-50%, -130%) scale(10.0); } /* Starts right up against the lens */
  1%   { opacity: 1; transform: translate(-50%, -130%) scale(10.0); } 
  15%  { opacity: 1; transform: translate(-50%, -80%) scale(5.8); } /* Drives to scan position */
  70%  { opacity: 1; transform: translate(-50%, -140%) scale(5.5); } /* STOPS to be scanned */
  90%  { opacity: 1; transform: translate(-50%, -130%) scale(3.7); } /* STOPS to be scanned */
  99%  { opacity: 1; transform: translate(-50%, -50%) scale(0.2); } /* Drives far away */
  100% { opacity: 0; transform: translate(-50%, -50%) scale(0.2); } 
}
.run-motor-back { animation: motorBackSequence 12s linear forwards; }
</style>
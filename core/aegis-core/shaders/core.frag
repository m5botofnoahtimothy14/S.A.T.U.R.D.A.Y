#version 450

/**
 * AEGIS Core Fragment Shader
 * 
 * Energy sphere rendering with:
 * - Fresnel glow effect
 * - Audio-reactive color modulation
 * - State-based color schemes
 * - Procedural energy patterns
 */

in vec3 vNormal;
in vec3 vPosition;
in vec2 vTexCoord;
in float vDisplacement;

out vec4 fragColor;

// Uniforms
uniform vec3 uCoreColor;
uniform vec3 uGlowColor;
uniform vec3 uInnerColor;

uniform float uTime;
uniform float uBass;
uniform float uMid;
uniform float uTreble;
uniform float uOverall;

uniform vec3 uCameraPosition;
uniform float uOpacity;

// State colors for different modes
const vec3 AMBER = vec3(1.0, 0.7, 0.0);      // Idle - warm amber
const vec3 GOLD = vec3(1.0, 0.85, 0.0);       // Speaking - golden
const vec3 COOL_BLUE = vec3(0.3, 0.5, 1.0);   // Listening - cool blue
const vec3 VIOLET = vec3(0.6, 0.2, 0.8);      // Secure - violet
const vec3 CYAN = vec3(0.0, 1.0, 1.0);        // Transfer - cyan

// Procedural patterns
float fresnel(vec3 viewDir, vec3 normal, float power) {
    return pow(1.0 - max(dot(viewDir, normal), 0.0), power);
}

float energyPattern(vec3 pos, float time) {
    // Rotating energy bands
    float angle = atan(pos.z, pos.x);
    float bands = sin(angle * 8.0 + time * 2.0) * 0.5 + 0.5;
    
    // Vertical waves
    float waves = sin(pos.y * 4.0 + time * 3.0) * 0.5 + 0.5;
    
    return bands * waves;
}

void main() {
    vec3 normal = normalize(vNormal);
    vec3 viewDir = normalize(uCameraPosition - vPosition);
    
    // Fresnel effect for edge glow
    float fresnelTerm = fresnel(viewDir, normal, 2.5);
    
    // Energy pattern
    float energy = energyPattern(normalize(vPosition), uTime);
    
    // Audio-reactive color modulation
    vec3 baseColor = uCoreColor;
    vec3 glowColor = uGlowColor;
    vec3 innerColor = uInnerColor;
    
    // Modulate based on audio
    float audioBoost = uOverall * 0.3;
    baseColor = mix(baseColor, GOLD, audioBoost);
    
    // Displacement affects brightness
    float displacementGlow = vDisplacement * 2.0 + 0.5;
    
    // Core glow - brighter at center
    float coreGlow = 1.0 - fresnelTerm;
    coreGlow = pow(coreGlow, 1.5);
    
    // Combine colors
    vec3 finalColor = innerColor * coreGlow * displacementGlow;
    finalColor += glowColor * fresnelTerm * (0.5 + energy * 0.5);
    finalColor += baseColor * (1.0 - fresnelTerm) * 0.5;
    
    // Add audio-reactive pulsing
    float pulse = sin(uTime * 5.0) * 0.5 + 0.5;
    finalColor += uGlowColor * uOverall * pulse * 0.5;
    
    // Add subtle noise variation
    float noise = fract(sin(dot(vTexCoord, vec2(12.9898, 78.233))) * 43758.5453);
    finalColor += noise * 0.02;
    
    // Output with opacity
    float alpha = uOpacity * (0.7 + fresnelTerm * 0.3);
    
    fragColor = vec4(finalColor, alpha);
}

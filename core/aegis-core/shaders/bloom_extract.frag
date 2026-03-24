#version 450

/**
 * Bloom Post-Processing Shader
 * 
 * Multi-pass bloom effect for glowing energy effects
 */

// Vertex shader - fullscreen quad
layout(location = 0) in vec2 aPosition;
out vec2 vTexCoord;

void main() {
    vTexCoord = aPosition * 0.5 + 0.5;
    gl_Position = vec4(aPosition, 0.0, 1.0);
}

// Fragment shader - brightness extraction
uniform sampler2D uTexture;
uniform float uThreshold;

in vec2 vTexCoord;
out vec4 fragColor;

void main() {
    vec4 color = texture(uTexture, vTexCoord);
    float brightness = dot(color.rgb, vec3(0.2126, 0.7152, 0.0722));
    
    if (brightness > uThreshold) {
        fragColor = color;
    } else {
        fragColor = vec4(0.0);
    }
}

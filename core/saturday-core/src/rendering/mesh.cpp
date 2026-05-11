#include "mesh.h"
#include "core/logger.h"
#include <cmath>
#include <algorithm>

#ifdef _WIN32
    #include <windows.h>
    #include <GL/gl.h>
    #pragma comment(lib, "opengl32.lib")
#else
    #include <GL/gl.h>
#endif

namespace aegis {

Mesh::Mesh() = default;

Mesh::~Mesh() {
    if (vbo_) glDeleteBuffers(1, &vbo_);
    if (ebo_) glDeleteBuffers(1, &ebo_);
    if (vao_) glDeleteVertexArrays(1, &vao_);
}

Mesh::Mesh(Mesh&& other) noexcept
    : vertices_(std::move(other.vertices_))
    , indices_(std::move(other.indices_))
    , vao_(other.vao_)
    , vbo_(other.vbo_)
    , ebo_(other.ebo_)
    , vertex_count_(other.vertex_count_)
    , index_count_(other.index_count_)
    , draw_mode_(other.draw_mode_) {
    other.vao_ = 0;
    other.vbo_ = 0;
    other.ebo_ = 0;
}

Mesh& Mesh::operator=(Mesh&& other) noexcept {
    if (this != &other) {
        if (vao_) glDeleteVertexArrays(1, &vao_);
        if (vbo_) glDeleteBuffers(1, &vbo_);
        if (ebo_) glDeleteBuffers(1, &ebo_);
        
        vertices_ = std::move(other.vertices_);
        indices_ = std::move(other.indices_);
        vao_ = other.vao_;
        vbo_ = other.vbo_;
        ebo_ = other.ebo_;
        vertex_count_ = other.vertex_count_;
        index_count_ = other.index_count_;
        draw_mode_ = other.draw_mode_;
        
        other.vao_ = 0;
        other.vbo_ = 0;
        other.ebo_ = 0;
    }
    return *this;
}

void Mesh::set_vertices(const std::vector<Vertex>& vertices) {
    vertices_.clear();
    vertices_.reserve(vertices.size() * 8); // 8 floats per vertex
    for (const auto& v : vertices) {
        vertices_.insert(vertices_.end(), {v.position[0], v.position[1], v.position[2]});
        vertices_.insert(vertices_.end(), {v.normal[0], v.normal[1], v.normal[2]});
        vertices_.insert(vertices_.end(), {v.texcoord[0], v.texcoord[1]});
        vertices_.insert(vertices_.end(), {v.color[0], v.color[1], v.color[2], v.color[3]});
    }
    vertex_count_ = vertices.size();
}

void Mesh::set_vertices(const float* data, size_t count) {
    vertices_.assign(data, data + count);
    vertex_count_ = count / 8; // 8 floats per vertex
}

void Mesh::set_indices(const std::vector<uint32_t>& indices) {
    indices_ = indices;
    index_count_ = indices.size();
}

void Mesh::set_indices(const uint32_t* data, size_t count) {
    indices_.assign(data, data + count);
    index_count_ = count;
}

void Mesh::build() {
    if (vao_) {
        glDeleteVertexArrays(1, &vao_);
        glDeleteBuffers(1, &vbo_);
        if (index_count_ > 0) glDeleteBuffers(1, &ebo_);
    }
    
    glGenVertexArrays(1, &vao_);
    glGenBuffers(1, &vbo_);
    
    glBindVertexArray(vao_);
    
    glBindBuffer(GL_ARRAY_BUFFER, vbo_);
    glBufferData(GL_ARRAY_BUFFER, vertices_.size() * sizeof(float), 
                 vertices_.data(), GL_STATIC_DRAW);
    
    glEnableVertexAttribArray(0);
    glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 8 * sizeof(float), (void*)0);
    
    glEnableVertexAttribArray(1);
    glVertexAttribPointer(1, 3, GL_FLOAT, GL_FALSE, 8 * sizeof(float), (void*)(3 * sizeof(float)));
    
    glEnableVertexAttribArray(2);
    glVertexAttribPointer(2, 2, GL_FLOAT, GL_FALSE, 8 * sizeof(float), (void*)(6 * sizeof(float)));
    
    glEnableVertexAttribArray(3);
    glVertexAttribPointer(3, 4, GL_FLOAT, GL_FALSE, 8 * sizeof(float), (void*)(8 * sizeof(float)));
    
    if (index_count_ > 0) {
        glGenBuffers(1, &ebo_);
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, ebo_);
        glBufferData(GL_ELEMENT_ARRAY_BUFFER, indices_.size() * sizeof(uint32_t),
                     indices_.data(), GL_STATIC_DRAW);
    }
    
    glBindVertexArray(0);
    
    AEGIS_DEBUG("Mesh", "Built mesh with " + std::to_string(vertex_count_) + " vertices");
}

void Mesh::upload() {
}

void Mesh::bind() const {
    glBindVertexArray(vao_);
}

void Mesh::unbind() {
    glBindVertexArray(0);
}

void Mesh::draw() const {
    if (index_count_ > 0) {
        glDrawElements(GL_TRIANGLES, static_cast<GLsizei>(index_count_), GL_UNSIGNED_INT, 0);
    } else if (vertex_count_ > 0) {
        glDrawArrays(GL_TRIANGLES, 0, static_cast<GLsizei>(vertex_count_));
    }
}

Mesh Mesh::create_sphere(float radius, int segments, int rings) {
    Mesh mesh;
    std::vector<Vertex> vertices;
    std::vector<uint32_t> indices;
    
    for (int ring = 0; ring <= rings; ++ring) {
        float theta = ring * 3.14159f / rings;
        float sin_theta = std::sin(theta);
        float cos_theta = std::cos(theta);
        
        for (int seg = 0; seg <= segments; ++seg) {
            float phi = seg * 2 * 3.14159f / segments;
            float sin_phi = std::sin(phi);
            float cos_phi = std::cos(phi);
            
            float x = cos_phi * sin_theta;
            float y = cos_theta;
            float z = sin_phi * sin_theta;
            
            Vertex v;
            v.position[0] = x * radius;
            v.position[1] = y * radius;
            v.position[2] = z * radius;
            v.normal[0] = x;
            v.normal[1] = y;
            v.normal[2] = z;
            v.texcoord[0] = (float)seg / segments;
            v.texcoord[1] = (float)ring / rings;
            
            vertices.push_back(v);
        }
    }
    
    for (int ring = 0; ring < rings; ++ring) {
        for (int seg = 0; seg < segments; ++seg) {
            uint32_t current = ring * (segments + 1) + seg;
            uint32_t next = current + segments + 1;
            
            indices.push_back(current);
            indices.push_back(next);
            indices.push_back(current + 1);
            
            indices.push_back(current + 1);
            indices.push_back(next);
            indices.push_back(next + 1);
        }
    }
    
    mesh.set_vertices(vertices);
    mesh.set_indices(indices);
    mesh.build();
    
    return mesh;
}

Mesh Mesh::create_torus(float major_radius, float minor_radius, int major_segments, int minor_segments) {
    Mesh mesh;
    std::vector<Vertex> vertices;
    std::vector<uint32_t> indices;
    
    for (int i = 0; i <= major_segments; ++i) {
        float u = (float)i / major_segments * 2 * 3.14159f;
        float cos_u = std::cos(u);
        float sin_u = std::sin(u);
        
        for (int j = 0; j <= minor_segments; ++j) {
            float v = (float)j / minor_segments * 2 * 3.14159f;
            float cos_v = std::cos(v);
            float sin_v = std::sin(v);
            
            float x = (major_radius + minor_radius * cos_v) * cos_u;
            float y = minor_radius * sin_v;
            float z = (major_radius + minor_radius * cos_v) * sin_u;
            
            Vertex vert;
            vert.position[0] = x;
            vert.position[1] = y;
            vert.position[2] = z;
            vert.normal[0] = cos_v * cos_u;
            vert.normal[1] = sin_v;
            vert.normal[2] = cos_v * sin_u;
            vert.texcoord[0] = (float)i / major_segments;
            vert.texcoord[1] = (float)j / minor_segments;
            
            vertices.push_back(vert);
        }
    }
    
    for (int i = 0; i < major_segments; ++i) {
        for (int j = 0; j < minor_segments; ++j) {
            uint32_t a = i * (minor_segments + 1) + j;
            uint32_t b = a + minor_segments + 1;
            
            indices.push_back(a);
            indices.push_back(b);
            indices.push_back(a + 1);
            
            indices.push_back(a + 1);
            indices.push_back(b);
            indices.push_back(b + 1);
        }
    }
    
    mesh.set_vertices(vertices);
    mesh.set_indices(indices);
    mesh.build();
    
    return mesh;
}

Mesh Mesh::create_plane(float width, float height, int segments) {
    Mesh mesh;
    std::vector<Vertex> vertices;
    std::vector<uint32_t> indices;
    
    float half_w = width / 2.0f;
    float half_h = height / 2.0f;
    
    for (int y = 0; y <= segments; ++y) {
        for (int x = 0; x <= segments; ++x) {
            float u = (float)x / segments;
            float v = (float)y / segments;
            
            Vertex vert;
            vert.position[0] = (u - 0.5f) * width;
            vert.position[1] = 0;
            vert.position[2] = (v - 0.5f) * height;
            vert.normal[0] = 0;
            vert.normal[1] = 1;
            vert.normal[2] = 0;
            vert.texcoord[0] = u;
            vert.texcoord[1] = v;
            
            vertices.push_back(vert);
        }
    }
    
    for (int y = 0; y < segments; ++y) {
        for (int x = 0; x < segments; ++x) {
            uint32_t a = y * (segments + 1) + x;
            uint32_t b = a + segments + 1;
            
            indices.push_back(a);
            indices.push_back(b);
            indices.push_back(a + 1);
            
            indices.push_back(a + 1);
            indices.push_back(b);
            indices.push_back(b + 1);
        }
    }
    
    mesh.set_vertices(vertices);
    mesh.set_indices(indices);
    mesh.build();
    
    return mesh;
}

Mesh Mesh::create_quad() {
    return create_plane(2.0f, 2.0f);
}

Mesh Mesh::create_particle_system(size_t count) {
    Mesh mesh;
    std::vector<Vertex> vertices(count);
    std::vector<uint32_t> indices(count);
    
    for (size_t i = 0; i < count; ++i) {
        vertices[i].position[0] = 0;
        vertices[i].position[1] = 0;
        vertices[i].position[2] = 0;
        
        vertices[i].color[0] = (rand() % 100) / 100.0f;
        vertices[i].color[1] = (rand() % 100) / 100.0f;
        vertices[i].color[2] = (rand() % 100) / 100.0f;
        
        indices[i] = static_cast<uint32_t>(i);
    }
    
    mesh.set_vertices(vertices);
    mesh.set_indices(indices);
    mesh.draw_mode_ = GL_POINTS;
    mesh.build();
    
    return mesh;
}

MeshBuilder& MeshBuilder::sphere(float radius, int segments, int rings) {
    mesh_ = Mesh::create_sphere(radius, segments, rings);
    return *this;
}

MeshBuilder& MeshBuilder::torus(float major_radius, float minor_radius, int major, int minor) {
    mesh_ = Mesh::create_torus(major_radius, minor_radius, major, minor);
    return *this;
}

MeshBuilder& MeshBuilder::plane(float width, float height) {
    mesh_ = Mesh::create_plane(width, height);
    return *this;
}

MeshBuilder& MeshBuilder::quad() {
    mesh_ = Mesh::create_quad();
    return *this;
}

MeshBuilder& MeshBuilder::particles(size_t count) {
    mesh_ = Mesh::create_particle_system(count);
    return *this;
}

Mesh MeshBuilder::build() {
    return std::move(mesh_);
}

} // namespace aegis

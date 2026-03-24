#pragma once

#include <vector>
#include <string>
#include <cstdint>
#include <cmath>

#include <GL/gl.h>

namespace aegis {

/**
 * @struct Vertex
 * @brief Vertex format for 3D rendering
 */
struct Vertex {
    float position[3];
    float normal[3];
    float texcoord[2];
    float color[4];
    
    Vertex() : position{0, 0, 0}, normal{0, 1, 0}, texcoord{0, 0}, color{1, 1, 1, 1} {}
};

/**
 * @class Mesh
 * @brief 3D mesh with GPU buffer management
 */
class Mesh {
public:
    Mesh();
    ~Mesh();
    
    // Non-copyable
    Mesh(const Mesh&) = delete;
    Mesh& operator=(const Mesh&) = delete;
    
    // Movable
    Mesh(Mesh&& other) noexcept;
    Mesh& operator=(Mesh&& other) noexcept;
    
    /**
     * @brief Set vertex data
     */
    void set_vertices(const std::vector<Vertex>& vertices);
    void set_vertices(const float* data, size_t count);
    
    /**
     * @brief Set index data
     */
    void set_indices(const std::vector<uint32_t>& indices);
    void set_indices(const uint32_t* data, size_t count);
    
    /**
     * @brief Build mesh from data
     */
    void build();
    
    /**
     * @brief Upload data to GPU
     */
    void upload();
    
    /**
     * @brief Bind VAO for rendering
     */
    void bind() const;
    
    /**
     * @brief Unbind VAO
     */
    static void unbind();
    
    /**
     * @brief Draw the mesh
     */
    void draw() const;
    
    // Getters
    size_t get_vertex_count() const { return vertex_count_; }
    size_t get_index_count() const { return index_count_; }
    bool is_indexed() const { return index_count_ > 0; }
    
    /**
     * @brief Create a sphere mesh
     */
    static Mesh create_sphere(float radius, int segments, int rings);
    
    /**
     * @brief Create a ring/torus mesh
     */
    static Mesh create_torus(float major_radius, float minor_radius, int major_segments, int minor_segments);
    
    /**
     * @brief Create a plane mesh
     */
    static Mesh create_plane(float width, float height, int segments = 1);
    
    /**
     * @brief Create a fullscreen quad
     */
    static Mesh create_quad();
    
    /**
     * @brief Create a point cloud
     */
    static Mesh create_particle_system(size_t count);
    
private:
    std::vector<float> vertices_;
    std::vector<uint32_t> indices_;
    
    GLuint vao_ = 0;
    GLuint vbo_ = 0;
    GLuint ebo_ = 0;
    
    size_t vertex_count_ = 0;
    size_t index_count_ = 0;
    
    GLenum draw_mode_ = GL_TRIANGLES;
};

/**
 * @class MeshBuilder
 * @brief Fluent builder for mesh generation
 */
class MeshBuilder {
public:
    MeshBuilder& sphere(float radius, int segments = 32, int rings = 16);
    MeshBuilder& torus(float major_radius, float minor_radius, int major = 32, int minor = 16);
    MeshBuilder& plane(float width, float height);
    MeshBuilder& quad();
    MeshBuilder& particles(size_t count);
    
    Mesh build();
    
private:
    Mesh mesh_;
};

} // namespace aegis

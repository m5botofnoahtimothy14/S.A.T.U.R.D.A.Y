cmake_minimum_required(VERSION 3.10)
project(AEGIS_AI_System)

# Find Python 3
find_package(Python3 REQUIRED COMPONENTS Interpreter Development)

message(STATUS "AEGIS Build System Initialized")
message(STATUS "Python Interpreter: ${Python3_EXECUTABLE}")

# Custom target to install dependencies
add_custom_target(install_deps
    COMMAND ${Python3_EXECUTABLE} -m pip install -r ${CMAKE_SOURCE_DIR}/requirements.txt
    WORKING_DIRECTORY ${CMAKE_SOURCE_DIR}
    COMMENT "Installing AEGIS Dependencies..."
)

# Custom target to setup venv
add_custom_target(setup_venv
    COMMAND ${Python3_EXECUTABLE} -m venv .venv
    WORKING_DIRECTORY ${CMAKE_SOURCE_DIR}
    COMMENT "Creating Virtual Environment..."
)

# Custom target to run AEGIS
add_custom_target(run
    COMMAND ${CMAKE_SOURCE_DIR}/.venv/Scripts/python core/main.py
    WORKING_DIRECTORY ${CMAKE_SOURCE_DIR}
    COMMENT "Starting AEGIS Core..."
)

# Installation logic
install(DIRECTORY core ai_modules identity communication health sensors ui services governance christianity_core
        DESTINATION bin)
install(FILES requirements.txt DESTINATION bin)

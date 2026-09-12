cmake_minimum_required(VERSION 4.3)
project(
	CGX
	VERSION 0.0.0
	DESCRIPTION "Compiler Generation eXplorer"
	LANGUAGES CXX
)

cmake_policy(SET CMP0207 NEW)

set(CMAKE_CXX_STANDARD 23)
add_compile_options(-fdiagnostics-color=always)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)
set(CMAKE_RUNTIME_OUTPUT_DIRECTORY ${CMAKE_SOURCE_DIR}/build)

add_subdirectory(analyzer)

set(EXE_NAME "analyzer")

add_subdirectory(${CMAKE_SOURCE_DIR}/external/CLI11 ${CMAKE_BINARY_DIR}/CLI11)

file(GLOB_RECURSE SOURCES src/*.cpp)

add_executable(${EXE_NAME} ${SOURCES})

# The build tree already contains an "analyzer" directory for this target's
# object files. Keep the executable in a separate directory to avoid a
# file/directory name collision at ${CMAKE_BINARY_DIR}/analyzer.
set_target_properties(${EXE_NAME} PROPERTIES
	RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
)

target_include_directories(${EXE_NAME} PRIVATE
	${CMAKE_SOURCE_DIR}/analyzer/src
	${CMAKE_SOURCE_DIR}/external
)

target_link_libraries(${EXE_NAME} PRIVATE CLI11::CLI11)

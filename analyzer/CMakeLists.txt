set(EXE_NAME "analyzer")

file(GLOB_RECURSE SOURCES src/*.cpp)

add_executable(${EXE_NAME} ${SOURCES})

target_include_directories(${EXE_NAME} PRIVATE
	${CMAKE_SOURCE_DIR}/analyzer/src
	${CMAKE_SOURCE_DIR}/external
)

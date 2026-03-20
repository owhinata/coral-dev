cmake_minimum_required(VERSION 3.16)
project(hello_world C)

add_executable(hello_world src/main.c)

# Deploy / Run
include(${CMAKE_CURRENT_LIST_DIR}/../../cmake/coral-deploy.cmake)

coral_add_deploy_target(
    DEPLOY_DIR /home/mendel/work/hello_world
    DEPENDS hello_world
    FILES "$<TARGET_FILE:hello_world>:hello_world"
)

coral_add_run_target(
    COMMAND /home/mendel/work/hello_world/hello_world
)

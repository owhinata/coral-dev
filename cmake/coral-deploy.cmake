# cmake/coral-deploy.cmake — shared Coral Dev Board deploy/run infrastructure

# --- Coral device cache variables ---
set(CORAL_IP "" CACHE STRING "Coral Dev Board IP address (empty = auto-detect via mdt)")
set(CORAL_USER "mendel" CACHE STRING "SSH user for Coral Dev Board")

set(_CORAL_SCRIPTS_DIR "${CMAKE_CURRENT_LIST_DIR}/scripts")

# --- coral_add_deploy_target() ---
# Arguments: DEPLOY_DIR, DEPENDS, FILES (local:remote ...)
function(coral_add_deploy_target)
    cmake_parse_arguments(ARG "" "DEPLOY_DIR" "DEPENDS;FILES" ${ARGN})
    add_custom_target(deploy
        COMMAND ${CMAKE_COMMAND} -E env
                "CORAL_USER=${CORAL_USER}"
                "CORAL_IP=${CORAL_IP}"
                "CORAL_DEPLOY_DIR=${ARG_DEPLOY_DIR}"
                ${_CORAL_SCRIPTS_DIR}/deploy.sh
                ${ARG_FILES}
        DEPENDS ${ARG_DEPENDS}
        USES_TERMINAL
        COMMENT "Deploying to Coral Dev Board (${ARG_DEPLOY_DIR})"
    )
endfunction()

# --- coral_add_run_target() ---
# Arguments: COMMAND (command string to execute on Coral)
function(coral_add_run_target)
    cmake_parse_arguments(ARG "" "COMMAND" "" ${ARGN})
    add_custom_target(run
        COMMAND ${CMAKE_COMMAND} -E env
                "CORAL_USER=${CORAL_USER}"
                "CORAL_IP=${CORAL_IP}"
                ${_CORAL_SCRIPTS_DIR}/run.sh
                "${ARG_COMMAND}"
        USES_TERMINAL
        COMMENT "Running on Coral Dev Board"
    )
endfunction()

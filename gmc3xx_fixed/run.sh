#!/usr/bin/with-contenv bashio
set -u

PORT_SETTING="$(bashio::config 'port')"
BAUD_SETTING="$(bashio::config 'baud')"
MANUAL_MQTT_SERVER="$(bashio::config 'mqtt_server')"
MANUAL_MQTT_PORT="$(bashio::config 'mqtt_port')"
MANUAL_MQTT_USER="$(bashio::config 'mqtt_user')"
MANUAL_MQTT_PASSWORD="$(bashio::config 'mqtt_password')"
DELAY="$(bashio::config 'repeat')"

RETRY_SECONDS=5
MQTT_TIMEOUT_SECONDS=15
HEALTH_PORT=38121
HEALTH_PID=""
RESOLVED_PORT=""
MQTT_SERVER=""
MQTT_PORT=""
MQTT_USER=""
MQTT_PASSWORD=""
MQTT_SSL="false"
MQTT_AUTO=0

cleanup() {
    if [[ -n "${HEALTH_PID}" ]] && kill -0 "${HEALTH_PID}" 2>/dev/null; then
        kill "${HEALTH_PID}" 2>/dev/null || true
        wait "${HEALTH_PID}" 2>/dev/null || true
    fi
}
trap cleanup EXIT
trap 'exit 0' TERM INT

start_health_endpoint() {
    local root="/tmp/gmc3xx-health"
    mkdir -p "${root}"
    printf 'ok\n' > "${root}/index.html"
    busybox httpd -f -p "${HEALTH_PORT}" -h "${root}" >/dev/null 2>&1 &
    HEALTH_PID=$!
}

port_description() {
    local port="$1"
    if [[ "${port}" == /dev/serial/by-id/* ]]; then
        printf 'USB serial device (stable by-id path; identifier hidden)'
    else
        printf '%s' "${port}"
    fi
}

resolve_port() {
    RESOLVED_PORT=""

    if [[ "${PORT_SETTING}" != "auto" ]]; then
        if [[ -e "${PORT_SETTING}" ]]; then
            RESOLVED_PORT="${PORT_SETTING}"
            return 0
        fi
        return 1
    fi

    shopt -s nullglob
    local candidates=(
        /dev/serial/by-id/*
        /dev/ttyUSB*
        /dev/ttyACM*
    )
    shopt -u nullglob

    if [[ ${#candidates[@]} -eq 0 ]]; then
        return 1
    fi

    local -A seen=()
    local matches=()
    local candidate real identity

    for candidate in "${candidates[@]}"; do
        [[ -e "${candidate}" ]] || continue
        real="$(readlink -f "${candidate}" 2>/dev/null || true)"
        [[ -n "${real}" ]] || real="${candidate}"
        if [[ -n "${seen[${real}]:-}" ]]; then
            continue
        fi
        seen["${real}"]=1

        identity=""
        if identity="$(gmc320 --identify "${candidate}" "${BAUD_SETTING}" 2>/dev/null)" \
            && printf '%s' "${identity}" | jq -e '.version and .serial and .serial_full and .baud' >/dev/null 2>&1; then
            matches+=("${candidate}")
        fi
    done

    if [[ ${#matches[@]} -eq 1 ]]; then
        RESOLVED_PORT="${matches[0]}"
        return 0
    fi

    if [[ ${#matches[@]} -gt 1 ]]; then
        bashio::log.error "More than one compatible GMC counter was found. Choose the serial device explicitly in the app configuration."
        return 2
    fi

    return 1
}

resolve_mqtt() {
    if [[ -n "${MANUAL_MQTT_SERVER}" ]]; then
        MQTT_AUTO=0
        MQTT_SERVER="${MANUAL_MQTT_SERVER}"
        MQTT_PORT="${MANUAL_MQTT_PORT}"
        MQTT_USER="${MANUAL_MQTT_USER}"
        MQTT_PASSWORD="${MANUAL_MQTT_PASSWORD}"
        MQTT_SSL="false"
        return 0
    fi

    local host port user password ssl
    host="$(bashio::services mqtt 'host' 2>/dev/null || true)"
    port="$(bashio::services mqtt 'port' 2>/dev/null || true)"
    user="$(bashio::services mqtt 'username' 2>/dev/null || true)"
    password="$(bashio::services mqtt 'password' 2>/dev/null || true)"
    ssl="$(bashio::services mqtt 'ssl' 2>/dev/null || true)"

    if [[ -z "${host}" || -z "${port}" ]]; then
        return 1
    fi

    MQTT_AUTO=1
    MQTT_SERVER="${host}"
    MQTT_PORT="${port}"
    MQTT_USER="${user}"
    MQTT_PASSWORD="${password}"
    MQTT_SSL="${ssl:-false}"
    return 0
}

build_mqtt_args() {
    local topic="$1"
    MQTT_ARGS=(
        -h "${MQTT_SERVER}"
        -p "${MQTT_PORT}"
        -t "${topic}"
        -q 0
    )

    if [[ -n "${MQTT_USER}" ]]; then
        MQTT_ARGS+=( -u "${MQTT_USER}" )
    fi
    if [[ -n "${MQTT_PASSWORD}" ]]; then
        MQTT_ARGS+=( -P "${MQTT_PASSWORD}" )
    fi
    if [[ "${MQTT_SSL}" == "true" ]]; then
        MQTT_ARGS+=( --tls-use-os-certs )
    fi
}

mqtt_publish_once() {
    local topic="$1"
    local payload="$2"
    build_mqtt_args "${topic}"
    timeout "${MQTT_TIMEOUT_SECONDS}s" \
        mosquitto_pub "${MQTT_ARGS[@]}" -m "${payload}" >/dev/null 2>&1
}

publish_payload() {
    local topic="$1"
    local payload="$2"

    if mqtt_publish_once "${topic}" "${payload}"; then
        return 0
    fi

    # Home Assistant can rotate the temporary credentials it gives apps. If
    # the automatic connection fails, ask Supervisor for the current service
    # details and try once more before giving up on this sample.
    if [[ ${MQTT_AUTO} -eq 1 ]] && resolve_mqtt; then
        if mqtt_publish_once "${topic}" "${payload}"; then
            return 0
        fi
    fi

    return 1
}

start_health_endpoint

bashio::log.info "Starting GMC3xx Radiation Monitor"
bashio::log.info "Serial device setting: ${PORT_SETTING}"
bashio::log.info "Baud setting: ${BAUD_SETTING}"
bashio::log.info "Polling interval: ${DELAY}s"

MQTT_MODE_LOGGED=""

while true; do
    if ! resolve_mqtt; then
        bashio::log.warning "Home Assistant's MQTT service is not available yet; retrying in ${RETRY_SECONDS}s"
        sleep "${RETRY_SECONDS}"
        continue
    fi

    if [[ ${MQTT_AUTO} -eq 1 && "${MQTT_MODE_LOGGED}" != "auto" ]]; then
        bashio::log.info "MQTT: using Home Assistant's MQTT service"
        MQTT_MODE_LOGGED="auto"
    elif [[ ${MQTT_AUTO} -eq 0 && "${MQTT_MODE_LOGGED}" != "manual" ]]; then
        bashio::log.info "MQTT: using the broker from app configuration"
        MQTT_MODE_LOGGED="manual"
    fi

    resolve_port
    rc=$?
    if [[ ${rc} -ne 0 ]]; then
        if [[ ${rc} -eq 2 ]]; then
            sleep "${RETRY_SECONDS}"
            continue
        fi
        if [[ "${PORT_SETTING}" == "auto" ]]; then
            bashio::log.warning "No compatible GMC counter is available yet; retrying in ${RETRY_SECONDS}s"
        else
            bashio::log.warning "The configured serial device is not available yet; retrying in ${RETRY_SECONDS}s"
        fi
        sleep "${RETRY_SECONDS}"
        continue
    fi

    bashio::log.info "Serial device: $(port_description "${RESOLVED_PORT}")"

    LAST_MQTT_WARNING=0
    MQTT_WAS_DOWN=0

    gmc320 --stream "${RESOLVED_PORT}" "${BAUD_SETTING}" "${DELAY}" \
        2> >(while IFS= read -r serial_message; do
            bashio::log.warning "${serial_message}"
        done) \
        | while IFS= read -r line; do
            if ! printf '%s' "${line}" | jq -e '.type' >/dev/null 2>&1; then
                bashio::log.warning "Ignored an unreadable message from the serial reader"
                continue
            fi

            record_type="$(printf '%s' "${line}" | jq -r '.type')"

            if [[ "${record_type}" == "identity" ]]; then
                if ! printf '%s' "${line}" | jq -e '.version and .serial and .serial_full and .baud' >/dev/null 2>&1; then
                    bashio::log.warning "The counter identity response was incomplete; reconnecting"
                    break
                fi

                version="$(printf '%s' "${line}" | jq -r '.version')"
                baud="$(printf '%s' "${line}" | jq -r '.baud')"
                has_diagnostics="$(printf '%s' "${line}" | jq -r 'if (.has_temp == true or .has_gyro == true) then "yes" else "no" end')"

                bashio::log.info "Detected device family: ${version}"
                bashio::log.info "Active serial baud: ${baud}"
                if [[ "${has_diagnostics}" == "yes" ]]; then
                    bashio::log.info "GMC-320 temperature/gyroscope readings are enabled"
                else
                    bashio::log.info "GMC-320-only temperature/gyroscope readings are not used for this model"
                fi
                bashio::log.info "Connected. Measurements are now being sent to MQTT."
                continue
            fi

            if [[ "${record_type}" != "sample" ]]; then
                continue
            fi

            if ! printf '%s' "${line}" | jq -e \
                '.serial and .serial_full and .version and .baud and has("cpm") and has("volt") and has("temp") and has("x") and has("y") and has("z") and .cpm != null and .volt != null' \
                >/dev/null 2>&1; then
                bashio::log.warning "Rejected an incomplete serial sample; nothing was published"
                continue
            fi

            serial="$(printf '%s' "${line}" | jq -r '.serial')"
            topic="homeassistant/sensor/gmc3xx_${serial}"
            payload="$(printf '%s' "${line}" | jq -c 'del(.type)')"

            if publish_payload "${topic}" "${payload}"; then
                if [[ ${MQTT_WAS_DOWN} -eq 1 ]]; then
                    bashio::log.info "MQTT publishing recovered"
                fi
                MQTT_WAS_DOWN=0
            else
                MQTT_WAS_DOWN=1
                now="$(date +%s)"
                if (( now - LAST_MQTT_WARNING >= 60 )); then
                    bashio::log.warning "MQTT publish failed; the app will keep retrying automatically"
                    LAST_MQTT_WARNING="${now}"
                fi
            fi
        done

    STREAM_RC=${PIPESTATUS[0]}
    if [[ ${STREAM_RC} -ne 0 ]]; then
        bashio::log.warning "Lost the serial connection; reconnecting in ${RETRY_SECONDS}s"
    else
        bashio::log.warning "Serial reader stopped; reconnecting in ${RETRY_SECONDS}s"
    fi
    sleep "${RETRY_SECONDS}"
done

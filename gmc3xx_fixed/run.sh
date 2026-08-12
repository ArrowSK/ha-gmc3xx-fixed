#!/usr/bin/with-contenv bashio
set -u

PORT="$(bashio::config 'port')"
BAUD_SETTING="$(bashio::config 'baud')"
MQTT_SERVER="$(bashio::config 'mqtt_server')"
MQTT_PORT="$(bashio::config 'mqtt_port')"
MQTT_USER="$(bashio::config 'mqtt_user')"
MQTT_PASSWORD="$(bashio::config 'mqtt_password')"
DELAY="$(bashio::config 'repeat')"

IDENTITY_RETRY_SECONDS=5
MQTT_TIMEOUT_SECONDS=15

bashio::log.info "Starting GMC3xx Fixed Radiation Monitor"
bashio::log.info "Serial device: ${PORT}"
bashio::log.info "Baud setting: ${BAUD_SETTING}"
bashio::log.info "Polling interval: ${DELAY}s"

# Never log the MQTT username/password or the detector serial number. Public bug
# reports should not need household-specific identifiers.
while [[ ! -e "${PORT}" ]]; do
    bashio::log.warning "Serial device ${PORT} is not present yet; retrying in ${IDENTITY_RETRY_SECONDS}s"
    sleep "${IDENTITY_RETRY_SECONDS}"
done

IDENTITY=""
while true; do
    if IDENTITY="$(gmc320 --identify "${PORT}" "${BAUD_SETTING}")" \
        && printf '%s' "${IDENTITY}" | jq -e '.version and .serial and .serial_full and .baud' >/dev/null 2>&1; then
        break
    fi
    bashio::log.warning "Unable to identify an RFC1201-compatible GMC counter; retrying in ${IDENTITY_RETRY_SECONDS}s"
    sleep "${IDENTITY_RETRY_SECONDS}"
done

VERSION="$(printf '%s' "${IDENTITY}" | jq -r '.version')"
SERIAL="$(printf '%s' "${IDENTITY}" | jq -r '.serial')"
SERIAL_FULL="$(printf '%s' "${IDENTITY}" | jq -r '.serial_full')"
BAUD="$(printf '%s' "${IDENTITY}" | jq -r '.baud')"
DIAGNOSTICS="$(printf '%s' "${IDENTITY}" | jq -r 'if (.has_temp == true or .has_gyro == true) then 1 else 0 end')"
TOPIC="homeassistant/sensor/gmc3xx_${SERIAL}"

bashio::log.info "Detected device family: ${VERSION}"
bashio::log.info "Active serial baud: ${BAUD}"
if [[ "${DIAGNOSTICS}" == "1" ]]; then
    bashio::log.info "GMC-320 diagnostics enabled (temperature/gyroscope)"
else
    bashio::log.info "GMC-320-only diagnostics disabled for this model"
fi
bashio::log.info "MQTT topic derived from detector serial (identifier redacted from log)"

build_mqtt_args() {
    MQTT_ARGS=(
        -h "${MQTT_SERVER}"
        -p "${MQTT_PORT}"
        -t "${TOPIC}"
        -q 0
    )

    if [[ -n "${MQTT_USER}" ]]; then
        MQTT_ARGS+=( -u "${MQTT_USER}" )
    fi
    if [[ -n "${MQTT_PASSWORD}" ]]; then
        MQTT_ARGS+=( -P "${MQTT_PASSWORD}" )
    fi
}

publish_payload() {
    local payload="$1"
    build_mqtt_args

    timeout "${MQTT_TIMEOUT_SECONDS}s" \
        mosquitto_pub "${MQTT_ARGS[@]}" -m "${payload}"
    local rc=$?
    if [[ ${rc} -ne 0 ]]; then
        if [[ ${rc} -eq 124 ]]; then
            bashio::log.warning "MQTT publish timed out after ${MQTT_TIMEOUT_SECONDS}s; sample was not published"
        else
            bashio::log.warning "MQTT publish failed (exit ${rc}); sample was not published"
        fi
        return 1
    fi
    return 0
}

bashio::log.info "Start sending data"
while true; do
    SAMPLE=""
    if SAMPLE="$(gmc320 --sample "${PORT}" "${BAUD}" "${DIAGNOSTICS}")" \
        && printf '%s' "${SAMPLE}" | jq -e 'has("cpm") and has("volt") and has("temp") and has("x") and has("y") and has("z") and .cpm != null and .volt != null' >/dev/null 2>&1; then

        DATA="$(jq -cn \
            --arg version "${VERSION}" \
            --arg serial "${SERIAL}" \
            --arg serial_full "${SERIAL_FULL}" \
            --argjson baud "${BAUD}" \
            --argjson sample "${SAMPLE}" \
            '{version:$version,serial:$serial,serial_full:$serial_full,baud:$baud} + $sample')"

        publish_payload "${DATA}" || true
    else
        bashio::log.warning "Rejected incomplete/malformed serial sample; nothing published this cycle"
    fi

    sleep "${DELAY}"
done

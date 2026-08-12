/*
 * GMC3xx serial reader for Home Assistant.
 *
 * Derived from gi1mic/gmc320 (GPL-3.0), which in turn notes that parts were
 * based on code by Christoph Haas.
 *
 * This version keeps the RFC1201 compatibility path while making serial
 * framing explicit: exact-length reads, stale-input draining, bounded retries,
 * model-aware optional commands, one persistent serial connection per run,
 * and fail-closed behavior when a response cannot be completed.
 *
 * SPDX-License-Identifier: GPL-3.0-only
 */

#define _DEFAULT_SOURCE

#include <errno.h>
#include <fcntl.h>
#include <poll.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <termios.h>
#include <time.h>
#include <unistd.h>

#define GMC_TIMEOUT_MS 1800
#define GMC_IDENTIFY_TIMEOUT_MS 900
#define GMC_RETRIES 3
#define GMC_INTER_COMMAND_US 25000
#define GMC_HEARTBEAT_SETTLE_US 500000

struct baud_entry {
    int rate;
    speed_t speed;
};

static const struct baud_entry BAUDS[] = {
    {115200, B115200},
    {57600, B57600},
    {19200, B19200},
    {38400, B38400},
    {9600, B9600},
    {4800, B4800},
    {2400, B2400},
    {1200, B1200},
#ifdef B14400
    {14400, B14400},
#endif
#ifdef B28800
    {28800, B28800},
#endif
};

struct identity {
    char version[32];
    char serial_compat[32];
    char serial_full[32];
    int baud;
    bool has_320_diagnostics;
};

struct sample {
    uint16_t cpm;
    double volt;
    bool has_temp;
    double temp;
    bool has_gyro;
    uint16_t x;
    uint16_t y;
    uint16_t z;
};

static long long monotonic_ms(void) {
    struct timespec ts;
    if (clock_gettime(CLOCK_MONOTONIC, &ts) != 0) {
        return 0;
    }
    return (long long)ts.tv_sec * 1000LL + ts.tv_nsec / 1000000LL;
}

static const struct baud_entry *find_baud(int rate) {
    for (size_t i = 0; i < sizeof(BAUDS) / sizeof(BAUDS[0]); ++i) {
        if (BAUDS[i].rate == rate) {
            return &BAUDS[i];
        }
    }
    return NULL;
}

static int parse_positive_int(const char *s, int *out) {
    char *end = NULL;
    errno = 0;
    long value = strtol(s, &end, 10);
    if (errno != 0 || end == s || *end != '\0' || value <= 0 || value > 1000000) {
        return -1;
    }
    *out = (int)value;
    return 0;
}

static int write_all(int fd, const uint8_t *buf, size_t len) {
    size_t off = 0;
    while (off < len) {
        ssize_t written = write(fd, buf + off, len - off);
        if (written > 0) {
            off += (size_t)written;
            continue;
        }
        if (written < 0 && errno == EINTR) {
            continue;
        }
        return -1;
    }
    return 0;
}

static int read_exact(int fd, uint8_t *buf, size_t len, int timeout_ms) {
    size_t off = 0;
    const long long deadline = monotonic_ms() + timeout_ms;

    while (off < len) {
        const long long now = monotonic_ms();
        const int remaining = (int)(deadline - now);
        if (remaining <= 0) {
            break;
        }

        struct pollfd pfd = {
            .fd = fd,
            .events = POLLIN,
            .revents = 0,
        };

        int prc = poll(&pfd, 1, remaining);
        if (prc == 0) {
            break;
        }
        if (prc < 0) {
            if (errno == EINTR) {
                continue;
            }
            return -1;
        }
        if (!(pfd.revents & (POLLIN | POLLHUP))) {
            return -1;
        }

        ssize_t got = read(fd, buf + off, len - off);
        if (got > 0) {
            off += (size_t)got;
            continue;
        }
        if (got < 0 && errno == EINTR) {
            continue;
        }
        if (got < 0 && (errno == EAGAIN || errno == EWOULDBLOCK)) {
            continue;
        }
        if (got == 0) {
            continue;
        }
        return -1;
    }

    return off == len ? 0 : -1;
}

static int flush_input(int fd) {
    if (tcflush(fd, TCIFLUSH) != 0) {
        fprintf(stderr, "serial: tcflush failed: %s\n", strerror(errno));
        return -1;
    }
    return 0;
}

static int transact_exact_opts(int fd, const char *cmd, uint8_t *reply,
                               size_t reply_len, int timeout_ms, int retries,
                               bool quiet) {
    for (int attempt = 1; attempt <= retries; ++attempt) {
        if (flush_input(fd) != 0) {
            return -1;
        }

        usleep(GMC_INTER_COMMAND_US);
        if (flush_input(fd) != 0) {
            return -1;
        }

        if (write_all(fd, (const uint8_t *)cmd, strlen(cmd)) != 0) {
            if (!quiet) {
                fprintf(stderr, "serial: write failed for %s: %s\n", cmd, strerror(errno));
            }
            return -1;
        }
        if (tcdrain(fd) != 0) {
            if (!quiet) {
                fprintf(stderr, "serial: tcdrain failed for %s: %s\n", cmd, strerror(errno));
            }
            return -1;
        }

        memset(reply, 0, reply_len);
        if (read_exact(fd, reply, reply_len, timeout_ms) == 0) {
            return 0;
        }

        if (!quiet && attempt < retries) {
            fprintf(stderr,
                    "serial: incomplete response for %s (attempt %d/%d); retrying\n",
                    cmd, attempt, retries);
        }
        usleep(50000);
    }

    if (!quiet) {
        fprintf(stderr, "serial: failed to obtain complete response for %s\n", cmd);
    }
    return -1;
}

static int transact_exact(int fd, const char *cmd, uint8_t *reply, size_t reply_len) {
    return transact_exact_opts(fd, cmd, reply, reply_len,
                               GMC_TIMEOUT_MS, GMC_RETRIES, false);
}

static int send_no_response(int fd, const char *cmd) {
    if (flush_input(fd) != 0) {
        return -1;
    }
    if (write_all(fd, (const uint8_t *)cmd, strlen(cmd)) != 0) {
        return -1;
    }
    if (tcdrain(fd) != 0) {
        return -1;
    }

    /* GMC-300-series firmware can ignore the first polling command when it
     * follows HEARTBEAT0 too quickly. The older reader effectively waited for
     * a 500 ms read timeout here; keep the same quiet period and then discard
     * bytes that were already in flight. */
    usleep(GMC_HEARTBEAT_SETTLE_US);
    return flush_input(fd);
}

static int open_serial(const char *device, int baud_rate) {
    const struct baud_entry *baud = find_baud(baud_rate);
    if (baud == NULL) {
        fprintf(stderr, "serial: unsupported baud rate %d\n", baud_rate);
        return -1;
    }

    int fd = open(device, O_RDWR | O_NOCTTY);
    if (fd < 0) {
        fprintf(stderr, "serial: cannot open device: %s\n", strerror(errno));
        return -1;
    }

    struct termios tio;
    if (tcgetattr(fd, &tio) != 0) {
        fprintf(stderr, "serial: tcgetattr failed: %s\n", strerror(errno));
        close(fd);
        return -1;
    }

    cfmakeraw(&tio);
    tio.c_cflag &= ~(PARENB | CSTOPB | CSIZE);
    tio.c_cflag |= CS8 | CREAD | CLOCAL;
#ifdef CRTSCTS
    tio.c_cflag &= ~CRTSCTS;
#endif
    tio.c_cc[VMIN] = 0;
    tio.c_cc[VTIME] = 1;

    if (cfsetispeed(&tio, baud->speed) != 0 || cfsetospeed(&tio, baud->speed) != 0) {
        fprintf(stderr, "serial: unable to set %d baud: %s\n", baud_rate, strerror(errno));
        close(fd);
        return -1;
    }

    if (tcsetattr(fd, TCSANOW, &tio) != 0) {
        fprintf(stderr, "serial: tcsetattr failed: %s\n", strerror(errno));
        close(fd);
        return -1;
    }

    if (flush_input(fd) != 0) {
        close(fd);
        return -1;
    }

    if (send_no_response(fd, "<HEARTBEAT0>>") != 0) {
        close(fd);
        return -1;
    }

    return fd;
}

static void json_print_string(const char *s) {
    putchar('"');
    for (const unsigned char *p = (const unsigned char *)s; *p; ++p) {
        switch (*p) {
            case '"': fputs("\\\"", stdout); break;
            case '\\': fputs("\\\\", stdout); break;
            case '\b': fputs("\\b", stdout); break;
            case '\f': fputs("\\f", stdout); break;
            case '\n': fputs("\\n", stdout); break;
            case '\r': fputs("\\r", stdout); break;
            case '\t': fputs("\\t", stdout); break;
            default:
                if (*p < 0x20) {
                    printf("\\u%04x", *p);
                } else {
                    putchar(*p);
                }
        }
    }
    putchar('"');
}

static void sanitize_ascii(char *dst, size_t dst_len, const uint8_t *src, size_t src_len) {
    size_t out = 0;
    for (size_t i = 0; i < src_len && out + 1 < dst_len; ++i) {
        const unsigned char ch = src[i];
        dst[out++] = (ch >= 0x20 && ch <= 0x7e) ? (char)ch : '?';
    }
    dst[out] = '\0';
}

static bool valid_rfc1201_version(const char *version) {
    return strncmp(version, "GMC-", 4) == 0 && strlen(version) >= 8;
}

static bool model_has_320_diagnostics(const char *version) {
    return strncmp(version, "GMC-320", 7) == 0;
}

static void format_serial_compat(char *dst, size_t dst_len, const uint8_t raw[7]) {
    size_t used = 0;
    dst[0] = '\0';

    /* Keep the old non-zero-padded %x formatting because existing Home
     * Assistant MQTT topics may depend on this exact identifier. */
    for (size_t i = 0; i < 7; ++i) {
        if (used >= dst_len) {
            break;
        }
        int n = snprintf(dst + used, dst_len - used, "%x", raw[i]);
        if (n < 0) {
            dst[0] = '\0';
            return;
        }
        if ((size_t)n >= dst_len - used) {
            dst[dst_len - 1] = '\0';
            return;
        }
        used += (size_t)n;
    }
}

static void format_serial_full(char *dst, size_t dst_len, const uint8_t raw[7]) {
    if (dst_len < 15) {
        if (dst_len > 0) {
            dst[0] = '\0';
        }
        return;
    }
    snprintf(dst, dst_len, "%02x%02x%02x%02x%02x%02x%02x",
             raw[0], raw[1], raw[2], raw[3], raw[4], raw[5], raw[6]);
}

static uint16_t decode_be16(const uint8_t bytes[2]) {
    return (uint16_t)(((uint16_t)bytes[0] << 8) | bytes[1]);
}

static int get_identity_on_fd(int fd, struct identity *identity, bool quick) {
    uint8_t ver_raw[14];
    uint8_t serial_raw[7];
    int rc;

    if (quick) {
        rc = transact_exact_opts(fd, "<GETVER>>", ver_raw, sizeof(ver_raw),
                                 GMC_IDENTIFY_TIMEOUT_MS, 1, true);
    } else {
        rc = transact_exact(fd, "<GETVER>>", ver_raw, sizeof(ver_raw));
    }
    if (rc != 0) {
        return -1;
    }

    sanitize_ascii(identity->version, sizeof(identity->version), ver_raw, sizeof(ver_raw));
    if (!valid_rfc1201_version(identity->version)) {
        return -1;
    }

    if (transact_exact(fd, "<GETSERIAL>>", serial_raw, sizeof(serial_raw)) != 0) {
        return -1;
    }

    format_serial_compat(identity->serial_compat, sizeof(identity->serial_compat), serial_raw);
    format_serial_full(identity->serial_full, sizeof(identity->serial_full), serial_raw);
    identity->has_320_diagnostics = model_has_320_diagnostics(identity->version);

    if (identity->serial_compat[0] == '\0' || identity->serial_full[0] == '\0') {
        fprintf(stderr, "serial: invalid empty identity response\n");
        return -1;
    }
    return 0;
}

static int identify_device(const char *device, const char *baud_spec,
                           int *fd_out, struct identity *identity) {
    memset(identity, 0, sizeof(*identity));

    if (strcmp(baud_spec, "auto") != 0) {
        int requested = 0;
        if (parse_positive_int(baud_spec, &requested) != 0 || find_baud(requested) == NULL) {
            fprintf(stderr, "serial: invalid/unsupported baud setting '%s'\n", baud_spec);
            return -1;
        }
        int fd = open_serial(device, requested);
        if (fd < 0) {
            return -1;
        }
        if (get_identity_on_fd(fd, identity, false) != 0) {
            close(fd);
            return -1;
        }
        identity->baud = requested;
        *fd_out = fd;
        return 0;
    }

    for (size_t i = 0; i < sizeof(BAUDS) / sizeof(BAUDS[0]); ++i) {
        int fd = open_serial(device, BAUDS[i].rate);
        if (fd < 0) {
            continue;
        }
        if (get_identity_on_fd(fd, identity, true) == 0) {
            identity->baud = BAUDS[i].rate;
            *fd_out = fd;
            return 0;
        }
        close(fd);
        memset(identity, 0, sizeof(*identity));
    }

    fprintf(stderr, "serial: no RFC1201-compatible GMC identity found at supported baud rates\n");
    return -1;
}

static int get_sample(int fd, bool enable_320_diagnostics, struct sample *out) {
    uint8_t cpm_raw[2];
    uint8_t volt_raw[1];

    memset(out, 0, sizeof(*out));

    if (transact_exact(fd, "<GETCPM>>", cpm_raw, sizeof(cpm_raw)) != 0) {
        return -1;
    }
    if (transact_exact(fd, "<GETVOLT>>", volt_raw, sizeof(volt_raw)) != 0) {
        return -1;
    }

    out->cpm = decode_be16(cpm_raw);
    out->volt = (double)volt_raw[0] / 10.0;

    if (!enable_320_diagnostics) {
        return 0;
    }

    uint8_t temp_raw[4];
    uint8_t gyro_raw[7];

    if (transact_exact(fd, "<GETTEMP>>", temp_raw, sizeof(temp_raw)) != 0) {
        return -1;
    }
    if (temp_raw[3] != 0xAA) {
        fprintf(stderr, "serial: invalid GETTEMP terminator 0x%02x; sample rejected\n",
                temp_raw[3]);
        return -1;
    }

    if (transact_exact(fd, "<GETGYRO>>", gyro_raw, sizeof(gyro_raw)) != 0) {
        return -1;
    }
    if (gyro_raw[6] != 0xAA) {
        fprintf(stderr, "serial: invalid GETGYRO terminator 0x%02x; sample rejected\n",
                gyro_raw[6]);
        return -1;
    }

    double temp = (double)temp_raw[0] + ((double)temp_raw[1] / 10.0);
    if (temp_raw[2] != 0) {
        temp = -temp;
    }
    out->has_temp = true;
    out->temp = temp;
    out->has_gyro = true;
    out->x = decode_be16(&gyro_raw[0]);
    out->y = decode_be16(&gyro_raw[2]);
    out->z = decode_be16(&gyro_raw[4]);
    return 0;
}

static void print_identity_json(const struct identity *identity, bool typed) {
    if (typed) {
        fputs("{\"type\":\"identity\",\"version\":", stdout);
    } else {
        fputs("{\"version\":", stdout);
    }
    json_print_string(identity->version);
    fputs(",\"serial\":", stdout);
    json_print_string(identity->serial_compat);
    fputs(",\"serial_full\":", stdout);
    json_print_string(identity->serial_full);
    printf(",\"baud\":%d,\"has_temp\":%s,\"has_gyro\":%s}\n",
           identity->baud,
           identity->has_320_diagnostics ? "true" : "false",
           identity->has_320_diagnostics ? "true" : "false");
}

static void print_sample_json(const struct sample *sample) {
    printf("{\"cpm\":%u,\"volt\":%.1f,\"temp\":", sample->cpm, sample->volt);
    if (sample->has_temp) {
        printf("%.1f", sample->temp);
    } else {
        fputs("null", stdout);
    }
    fputs(",\"x\":", stdout);
    if (sample->has_gyro) {
        printf("%u", sample->x);
    } else {
        fputs("null", stdout);
    }
    fputs(",\"y\":", stdout);
    if (sample->has_gyro) {
        printf("%u", sample->y);
    } else {
        fputs("null", stdout);
    }
    fputs(",\"z\":", stdout);
    if (sample->has_gyro) {
        printf("%u", sample->z);
    } else {
        fputs("null", stdout);
    }
    fputs("}\n", stdout);
}

static void print_stream_sample_json(const struct identity *identity,
                                     const struct sample *sample) {
    fputs("{\"type\":\"sample\",\"version\":", stdout);
    json_print_string(identity->version);
    fputs(",\"serial\":", stdout);
    json_print_string(identity->serial_compat);
    fputs(",\"serial_full\":", stdout);
    json_print_string(identity->serial_full);
    printf(",\"baud\":%d,\"cpm\":%u,\"volt\":%.1f,\"temp\":",
           identity->baud, sample->cpm, sample->volt);
    if (sample->has_temp) {
        printf("%.1f", sample->temp);
    } else {
        fputs("null", stdout);
    }
    fputs(",\"x\":", stdout);
    if (sample->has_gyro) {
        printf("%u", sample->x);
    } else {
        fputs("null", stdout);
    }
    fputs(",\"y\":", stdout);
    if (sample->has_gyro) {
        printf("%u", sample->y);
    } else {
        fputs("null", stdout);
    }
    fputs(",\"z\":", stdout);
    if (sample->has_gyro) {
        printf("%u", sample->z);
    } else {
        fputs("null", stdout);
    }
    fputs("}\n", stdout);
}

static int sleep_seconds(int seconds) {
    struct timespec req = {
        .tv_sec = seconds,
        .tv_nsec = 0,
    };
    while (nanosleep(&req, &req) != 0) {
        if (errno == EINTR) {
            continue;
        }
        return -1;
    }
    return 0;
}

static int stream_device(const char *device, const char *baud_spec, int interval) {
    int fd = -1;
    struct identity identity;
    if (identify_device(device, baud_spec, &fd, &identity) != 0) {
        return 1;
    }

    setvbuf(stdout, NULL, _IOLBF, 0);
    print_identity_json(&identity, true);
    fflush(stdout);

    while (true) {
        struct sample sample;
        if (get_sample(fd, identity.has_320_diagnostics, &sample) != 0) {
            close(fd);
            return 1;
        }
        print_stream_sample_json(&identity, &sample);
        fflush(stdout);

        if (sleep_seconds(interval) != 0) {
            fprintf(stderr, "serial: sleep failed: %s\n", strerror(errno));
            close(fd);
            return 1;
        }
    }
}

static void usage(const char *prog) {
    fprintf(stderr,
            "Usage:\n"
            "  %s --identify DEVICE BAUD|auto\n"
            "  %s --sample DEVICE BAUD DIAGNOSTICS\n"
            "  %s --stream DEVICE BAUD|auto INTERVAL_SECONDS\n"
            "\n"
            "DIAGNOSTICS is 1 only for GMC-320-family RFC1201 units; otherwise 0.\n",
            prog, prog, prog);
}

int main(int argc, char **argv) {
    if (argc == 4 && strcmp(argv[1], "--identify") == 0) {
        int fd = -1;
        struct identity identity;
        if (identify_device(argv[2], argv[3], &fd, &identity) != 0) {
            return 1;
        }
        print_identity_json(&identity, false);
        close(fd);
        return 0;
    }

    if (argc == 5 && strcmp(argv[1], "--sample") == 0) {
        int baud = 0;
        if (parse_positive_int(argv[3], &baud) != 0 || find_baud(baud) == NULL) {
            fprintf(stderr, "serial: invalid/unsupported sample baud '%s'\n", argv[3]);
            return 2;
        }
        if (strcmp(argv[4], "0") != 0 && strcmp(argv[4], "1") != 0) {
            fprintf(stderr, "serial: diagnostics flag must be 0 or 1\n");
            return 2;
        }

        int fd = open_serial(argv[2], baud);
        if (fd < 0) {
            return 1;
        }
        struct sample sample;
        int rc = get_sample(fd, strcmp(argv[4], "1") == 0, &sample);
        if (rc == 0) {
            print_sample_json(&sample);
        }
        close(fd);
        return rc == 0 ? 0 : 1;
    }

    if (argc == 5 && strcmp(argv[1], "--stream") == 0) {
        int interval = 0;
        if (parse_positive_int(argv[4], &interval) != 0 || interval < 2 || interval > 3600) {
            fprintf(stderr, "serial: stream interval must be between 2 and 3600 seconds\n");
            return 2;
        }
        return stream_device(argv[2], argv[3], interval);
    }

    usage(argv[0]);
    return 2;
}

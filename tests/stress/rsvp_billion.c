/* A deterministic model-checking stress test, NOT HTTP requests to the app.
 * One billion modeled RSVP operations: creation, idempotent retry, conflicting
 * retry, stale edit and authorized edit (including declines/reconfirmations).
 * Independent full recounts detect drift of buffet and souvenir dashboards.
 */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <inttypes.h>
#include <string.h>
#define FAMILY_SLOTS 4096u
#define AUDIT_INTERVAL ((uint64_t)1 << 21)
typedef struct {
    uint32_t revision;
    uint8_t registered, attending, participants, young, children;
} Family;
static uint32_t state = 0x29a13cc7u;
static uint32_t rnd(void) {
    state ^= state << 13;
    state ^= state >> 17;
    state ^= state << 5;
    return state;
}
static void panic(uint64_t index, const char *reason) {
    fprintf(stderr, "FAIL simulated_op=%" PRIu64 " %s\n", index, reason);
    exit(1);
}
static void check_family(const Family *family, uint64_t index) {
    if (!family->registered) {
        if (family->revision || family->attending || family->participants ||
                family->young || family->children)
            panic(index, "unregistered slot has data");
        return;
    }
    if (!family->revision || family->young > family->children ||
            family->children > family->participants)
        panic(index, "invalid guest counters or revision");
    if (!family->attending &&
            (family->participants || family->young || family->children))
        panic(index, "declined guest included in totals");
    if (family->attending && !family->participants)
        panic(index, "confirmed family lacks participants");
}
static Family next_record(uint32_t random, uint8_t attending, uint32_t revision) {
    Family entry = {0};
    entry.registered = 1;
    entry.attending = attending;
    entry.revision = revision;
    if (attending) {
        entry.participants = (uint8_t)(1u + (random & 7u));
        uint32_t ages = random >> 3;
        for (unsigned i=0; i<entry.participants; ++i) {
            unsigned category = ages % 3u; /* 0: 0-5, 1: 6-12, 2: >12 */
            entry.young += (category == 0u);
            entry.children += (category != 2u);
            ages = ages/3u + (ages ^ random)/17u;
        }
    }
    return entry;
}
static int64_t bcount(Family f) {return (int64_t)f.participants - f.young;}
static int64_t scount(Family f) {return f.children;}
static void audit(const Family *entries, int64_t buffet, int64_t souvenirs,
                  uint64_t index) {
    int64_t real_buffet=0, real_souvenirs=0;
    for (unsigned i=0; i<FAMILY_SLOTS; ++i) {
        check_family(&entries[i], index);
        real_buffet += bcount(entries[i]);
        real_souvenirs += scount(entries[i]);
    }
    if (buffet != real_buffet || souvenirs != real_souvenirs)
        panic(index, "global dashboard totals drift from independent recount");
}
int main(int argc, char **argv) {
    uint64_t iterations=UINT64_C(1000000000);
    if (argc>2) return 2;
    if (argc==2) {
        char *end=NULL;
        unsigned long long parsed=strtoull(argv[1], &end, 10);
        if (!argv[1][0] || *end || !parsed ||
                parsed>UINT64_C(1000000000)) return 2;
        iterations=(uint64_t)parsed;
    }
    Family entries[FAMILY_SLOTS]={0};
    uint64_t created=0, retries=0, conflicts=0, edits=0, stale=0, declines=0;
    int64_t buffet=0, souvenirs=0;
    for (uint64_t i=0; i<iterations; i++) {
        uint32_t bits=rnd();
        unsigned slot=bits & (FAMILY_SLOTS-1u);
        Family before=entries[slot];
        unsigned action=(bits>>12)&7u;
        if (!before.registered) {
            Family next=next_record(rnd(), (uint8_t)((bits>>20)&1u), 1);
            entries[slot]=next;
            buffet+=bcount(next); souvenirs+=scount(next); created++;
        } else if (action==0u || action==1u) {
            retries++;
            if (memcmp(&entries[slot], &before, sizeof(before)))
                panic(i, "same-key replay mutated family");
        } else if (action==2u) {
            conflicts++;
            if (memcmp(&entries[slot], &before, sizeof(before)))
                panic(i, "different-payload replay mutated family");
        } else if (action==3u) {
            stale++;
            if (memcmp(&entries[slot], &before, sizeof(before)))
                panic(i, "stale revision mutated family");
        } else {
            Family next=next_record(rnd(), (uint8_t)((bits>>21)&1u),
                                    before.revision+1u);
            buffet+=bcount(next)-bcount(before);
            souvenirs+=scount(next)-scount(before);
            entries[slot]=next; edits++; declines+=!next.attending;
        }
        if ((i&(AUDIT_INTERVAL-1u))==0) audit(entries, buffet, souvenirs, i);
    }
    audit(entries, buffet, souvenirs, iterations);
    if (created+retries+conflicts+stale+edits!=iterations)
        panic(iterations, "operation accounting mismatch");
    printf("PASS simulated_state_operations=%" PRIu64
           " unique_families=%" PRIu64 " idempotent_replays=%" PRIu64
           " conflicts=%" PRIu64 " stale_edits=%" PRIu64
           " updates=%" PRIu64 " declines=%" PRIu64
           " buffet=%" PRId64 " souvenirs=%" PRId64 "\n",
           iterations, created, retries, conflicts, stale, edits, declines,
           buffet, souvenirs);
    return 0;
}

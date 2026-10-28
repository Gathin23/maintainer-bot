## Policies from Rounds AA–AF (25–27 Oct)
Drafted from the round notes; Gathin to approve. Each line names the PRs it comes from.
- The bar: lean to closing low-value PRs, kindly. The core only takes switches most owners want. Look-only
  switches and niche top-bar buttons or rows are **closed** with a fork/SHOWCASE pointer, even small and tested,
  even when the bot leaned merge (#1748, #1830, #1863, #1864, #1965, #1966, #1995, #2001, #2002, #2010, #2067,
  #2125, #2133). Switches that fix a real problem for many owners can merge (#1964, #1994). Big new features,
  anything changing the default look, and taste calls go to the maintainer (**hold**).
- No new accessibility-service, notification-access or network add-ons in the repo (#1177, #1316, #1537, #1816,
  #1949, #1976); a separate app can be a SHOWCASE row (#1884, #1899). An add-on whose point is turning wireless
  debugging back on is a **hold** (#2066).
- A change to someone else's add-on (behaviour, permissions, install script) needs that add-on's author's OK:
  **rework** asking them (#1490, #1867, #1926, #1977, #2023). Strings or spacing only need no OK (#1978).
- Never point people at keeping network ADB or wireless debugging on, or turning ADB back on at boot: trim it on
  merge or close (#877, #1975, #1768, #2066).
- Lists: TV middleware (`com.cltv.*`, `tv.mopa.ginga`, the Live TV app) is commented out on merge (#1808, #1859,
  #1578). Shared lists keep the updater and the phone-remote service on, and the owner's own streaming apps are not
  disabled for everyone: comment them out with a line saying this set has them off (#1619, #1730, #2058).
- A list must have run on that TV, with its build and a reboot check: app-picked lists with no build or reboot
  details are closed (#1740).
- Second units: the same product code and the same build as a folder on main → **rework**, fold in as a unit
  (#2129). A different retail model, region or firmware line can be its own folder (#1710, #2108, #2120). Two PRs
  adding the same folder: the ready, reboot-checked one goes first, the other becomes its second unit
  (#2114/#1990, #2120 over #1621).
- Hold: drafts (#1990); commits *authored* by Claude, not just a Co-Authored-By trailer (#2098); Home/boot path
  changes without a real-TV run, ADB-closing logic, workflows, signing or package id (#1992); forks shipping APKs
  under our package name `com.gathin.tvhome` (#2150).
- Close: anything going around the China TCL install check (#1729); a workflow change that widens CI token
  permissions, flagged (#1883); day-old tools repos shipping prebuilt binaries under our name (#1742, #1768).
  Quick start stays on the one reviewed phone app (#1630).
- Docs PRs merge without a test that only pins a page's exact wording (#1791, #1821, #1828, #1882).

set(VCPKG_TARGET_ARCHITECTURE x64)
set(VCPKG_CRT_LINKAGE dynamic)
set(VCPKG_LIBRARY_LINKAGE dynamic)
set(VCPKG_BUILD_TYPE release)

# vcpkg's /OPT:ICF merges functions that CPython's typeobject.c tells apart
# by address, so put back the /OPT:NOICF that CPython links with
if(PORT STREQUAL "python3")
    set(VCPKG_LINKER_FLAGS "/OPT:NOICF")
endif()

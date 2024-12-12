#
# spec file for package go1.21
#
# Copyright (c) 2024 SUSE LLC
#
# All modifications and additions to the file contributed by third parties
# remain the property of their copyright owners, unless otherwise agreed
# upon. The license for this file, and modifications and additions to the
# file, is the same license as for the pristine package itself (unless the
# license for the pristine package is not an Open Source License, in which
# case the license is the MIT License). An "Open Source License" is a
# license that conforms to the Open Source Definition (Version 1.9)
# published by the Open Source Initiative.

%define gcc_go_version 13
%define go_bootstrap_version go1.18

# Bootstrap go toolchain using gccgo.
# To bootstrap using go, use '--without gccgo'
%bcond_without gccgo

# Build go-race only on platforms where C++14 is supported (SLE-15)
%define tsan_arch x86_64 aarch64 s390x ppc64le

# Go has precompiled versions of LLVM's compiler-rt inside their source code.
# We cannot ship pre-compiled binaries so we have to recompile said source,
# however they vendor specific commits from upstream. This value comes from
# src/runtime/race/README (and we verify that it matches in check).
#
# In order to update the TSAN version, modify _service. See boo#1052528 for
# more details.
%ifarch x86_64 %{?x86_64}
%define tsan_commit 74c2d4f6024c8f160871a2baa928d0b42415f183
%else
%define tsan_commit 41cb504b7c4b18ac15830107431a0c1eec73a6b2
%endif

# go_api is the major version of Go.
# Used by go1.x packages and go metapackage for:
# RPM Provides: golang(API), RPM Requires: and rpm_vercmp
# as well as derived variables such as go_label.
%define go_api 1.21

# go_label is the configurable Go toolchain directory name.
# Used for packaging multiple Go toolchains with the same go_api.
# go_label should be defined as go_api with optional suffix, e.g.
# go_api or go_api-foo
%define go_label %{go_api}

# shared library support
%if %{with gccgo}
%define with_shared 1
%else
%ifarch %ix86 %arm x86_64 aarch64
%define with_shared 1
%else
%define with_shared 0
%endif
%endif
%ifarch ppc64
%define with_shared 0
%endif
# setup go_arch (BSD-like scheme)
%ifarch %ix86
%define go_arch 386
%endif
%ifarch x86_64
%define go_arch amd64
# set GOAMD64 consistently
%define go_amd64 v1
%endif
%ifarch aarch64
%define go_arch arm64
%endif
%ifarch %arm
%define go_arch arm
%endif

Name:           go1.21
Version:        1.21.13
Release:        1
Summary:        A compiled, garbage-collected, concurrent programming language
License:        BSD-3-Clause
Group:          Development/Languages/Go
URL:            https://github.com/sailfishos-mirror/go/
Source:         %{name}-%{version}.tar.xz
Source1:        go-rpmlintrc
# For cases where go.env isn't available/created. From Go 1.21 binary rpm.
Source7:        go.env
# We have to compile TSAN ourselves. boo#1052528
# Preferred form when all arches share llvm race version
# Source100:      llvm-%%{tsan_commit}.tar.xz
Source100:      llvm-74c2d4f6024c8f160871a2baa928d0b42415f183.tar.xz
Source101:      llvm-41cb504b7c4b18ac15830107431a0c1eec73a6b2.tar.xz
# PATCH-FIX-UPSTREAM marguerite@opensuse.org - find /usr/bin/go.gcc when bootstrapping with gcc-go
Patch8:         gcc-go.patch
BuildRoot:      %{_tmppath}/%{name}-%{version}-build
# boostrap
%if %{with gccgo}
# FIXME when we have gcc 13
# BuildRequires:  gcc-go >= %%{gcc_go_version}
BuildRequires:  gcc-go
%else
# no gcc-go
BuildRequires:  %{go_bootstrap_version}
%endif
BuildRequires:  fdupes
Suggests:       %{name}-doc = %{version}
Suggests:       %{name}-libstd = %{version}
%ifarch %{tsan_arch}
# Needed to compile compiler-rt/TSAN.
BuildRequires:  gcc-c++
%endif
#BNC#818502 debug edit tool of rpm fails on i586 builds
BuildRequires:  rpm >= 4.11.1
Requires:       gcc

# BusyBox xargs doesn't support '-d'
BuildRequires:  gnu-findutils

Provides:       go = %{version}
Provides:       go-devel = go%{version}
Provides:       go-devel-static = go%{version}
Provides:       golang(API) = %{go_api}
Obsoletes:      go-devel < go%{version}
# go-vim/emacs were separate projects starting from 1.4
Obsoletes:      go-emacs <= 1.3.3
Obsoletes:      go-vim <= 1.3.3
ExclusiveArch:  %ix86 x86_64 %arm aarch64

%description
Go is an expressive, concurrent, garbage collected systems programming language
that is type safe and memory safe. It has pointers but no pointer arithmetic.
Go has fast builds, clean syntax, garbage collection, methods for any type, and
run-time reflection. It feels like a dynamic language but has the speed and
safety of a static language.

%package doc
Summary:        Go documentation
Group:          Documentation/Other
Provides:       go-doc = %{version}

%description doc
Go examples and documentation.

%ifarch %{tsan_arch}
# boo#1052528
%package race
Summary:        Go runtime race detector
Group:          Development/Languages/Go
URL:            https://compiler-rt.llvm.org/
Requires:       %{name} = %{version}
Supplements:    %{name} = %{version}
ExclusiveArch:  %{tsan_arch}

%description race
Go runtime race detector libraries. Install this package if you wish to use the
-race option, in order to detect race conditions present in your Go programs.
%endif

%if %{with_shared}
%package libstd
Summary:        Go compiled shared library libstd.so
Group:          Development/Languages/Go
Provides:       go-libstd = %{version}

%description libstd
Go standard library compiled to a dynamically loadable shared object libstd.so
%endif

%prep
%ifarch %{tsan_arch}
# compiler-rt (from LLVM)
%ifarch x86_64
%setup -q -T -b 100 -n llvm-%{tsan_commit}
%else
%setup -q -T -b 101 -n llvm-%{tsan_commit}
%endif
%endif

# go
%setup -q -n %{name}-%{version}
%if %{with gccgo}
# Currently gcc-go does not manage an update-alternatives entry and will
# never be symlinked as "go", even if gcc-go is the only installed go toolchain.
# Patch go bootstrap scripts to find hardcoded go-(gcc-go-version) e.g. go-8
# Substitute defined gcc_go_version into gcc-go.patch
pushd go
%patch -P 8 -p1
popd
%endif

%build

# FIXME: perhaps these should be patched in?
# See also .gitignore
export GOTMPDIR=${TMPDIR:-$(realpath ".tmp-go")}
mkdir -p $GOTMPDIR

export GOCACHE=${TMPDIR:-$(realpath ".tmp-gocache")}
mkdir -p $GOCACHE

export TMPDIR=${TMPDIR:-$(realpath ".tmp")}
mkdir -p $TMPDIR

# Remove the pre-included .sysos, to avoid shipping things we didn't compile
# (which is against the openSUSE guidelines for packaging).
find . -type f -name '*.syso' -print -delete

# First, compile LLVM's TSAN, and replace the built-in with it. We can only do
# this for amd64.
%ifarch %{tsan_arch}
TSAN_DIR="../llvm-%{tsan_commit}/compiler-rt/lib/tsan/go"
pushd "$TSAN_DIR"
./buildgo.sh
cp -v "$TSAN_DIR/race_linux_%{go_arch}.syso" src/runtime/race/
popd
%endif

# Now, compile Go.
%if %{with gccgo}
export GOROOT_BOOTSTRAP=%{_prefix}
%else
export GOROOT_BOOTSTRAP=%{_libdir}/%{go_bootstrap_version}
%endif
# Ensure ARM arch is set properly - boo#1169832
%ifarch armv6l armv6hl
export GOARCH=arm
export GOARM=6
%endif
%ifarch armv7l armv7hl
export GOARCH=arm
export GOARM=7
%endif
%ifarch aarch64
export GOARCH=arm64
%endif
%ifarch %ix86
export GOARCH=386
%endif
%ifarch x86_64 %{?x86_64}
# use the baseline defined above. Other option is GOAMD64=v3 for x86_64_v3 support
export GOARCH=amd64
export GOAMD64=%go_amd64
%endif
export GOROOT="`pwd`"/go
export GOROOT_FINAL=%{_libdir}/go/%{go_label}
export GOBIN="$GOROOT/bin"
mkdir -p "$GOBIN"
cd go/src
HOST_EXTRA_CFLAGS="%{optflags} -Wno-error" taskset 0x1 ./make.bash -v

cd ../
%ifarch %{tsan_arch}
# Install TSAN-friendly version of the std libraries.
pwd
bin/go install -race std
%endif
cd ../

%if %{with_shared}
# openSUSE Tumbleweed
# Compile Go standard library as a dynamically loaded shared object libstd.so
# for inclusion in a subpackage which can be installed standalone.
# Upstream Go binary releases do not ship a compiled libstd.so.
# Standard practice is to build Go binaries as a single executable.
# Upstream Go discussed removing this feature, opted to fix current support:
# Relevant upstream comments on: https://github.com/golang/go/issues/47788
#
# -buildmode=shared
#    Combine all the listed non-main packages into a single shared
#    library that will be used when building with the -linkshared
#    option. Packages named main are ignored.
#
# -linkshared
#    build code that will be linked against shared libraries previously
#    created with -buildmode=shared.
bin/go install -buildmode=shared std
%endif

%check
%ifarch %{tsan_arch}
# Make sure that we have the right TSAN checked out.
# As of go1.20, README x86_64 race_linux.syso
# includes path prefix and omits arch in filename e.g.
# internal/amd64v1/race_linux.syso
%ifarch x86_64 %{?x86_64}
grep "^internal/amd64%{go_amd64}/race_linux.syso built with LLVM %{tsan_commit}" go/src/runtime/race/README
%else
grep "^race_linux_%{go_arch}.syso built with LLVM %{tsan_commit}" go/src/runtime/race/README
%endif
%endif

%install
pushd go
export GOROOT="%{buildroot}%{_libdir}/go/%{go_label}"

# locations for third party libraries, see README-openSUSE for info about locations.
install -d  %{buildroot}%{_datadir}/go/%{go_label}/contrib
install -d  $GOROOT/contrib/pkg/linux_%{go_arch}
ln -s %{_libdir}/go/%{go_label}/contrib/pkg/ %{buildroot}%{_datadir}/go/%{go_label}/contrib/pkg
install -d  %{buildroot}%{_datadir}/go/%{go_label}/contrib/cmd
install -d  %{buildroot}%{_datadir}/go/%{go_label}/contrib/src
ln -s %{_datadir}/go/%{go_label}/contrib/src/ %{buildroot}%{_libdir}/go/%{go_label}/contrib/src

# go.env sets defaults for: GOPROXY GOSUMDB GOTOOLCHAIN
if [ -f go.env ]; then
  install -Dm644 go.env $GOROOT/
else
  install -Dm644 %{SOURCE7} $GOROOT/
fi

# Change go.env GOTOOLCHAIN default to "local" so Go app builds never
# automatically download newer toolchains as specified by go.mod files.
# When GOTOOLCHAIN is set to local, the go command always runs the bundled Go toolchain.
# See https://go.dev/doc/toolchain for details.
# The default behavior "auto":
# a) Assumes network access that is not available in OBS
# b) Downloads third-party toolchain binaries that would be used in build
# Need for "auto" is rare as openSUSE and SUSE ship go1.x versions near their release date.
# The user can override the defaults in ~/.config/go/env.
sed -i "s/GOTOOLCHAIN=auto/GOTOOLCHAIN=local/" $GOROOT/go.env

# source files for go install, godoc, etc
install -d %{buildroot}%{_datadir}/go/%{go_label}
for ext in *.{go,c,h,s,S,py,syso,bin}; do
  find src -name ${ext} -exec install -Dm644 \{\} %{buildroot}%{_datadir}/go/%{go_label}/\{\} \;
done
# executable bash scripts called by go tool, etc
find src -name "*.bash" -exec install -Dm655 \{\} %{buildroot}%{_datadir}/go/%{go_label}/\{\} \;
# VERSION file referenced by go tool dist and go tool distpack
find . -name VERSION -exec install -Dm655 \{\} %{buildroot}%{_datadir}/go/%{go_label}/\{\} \;
# Trace viewer html and javascript files moved from misc/trace in
# previous versions to src/cmd/trace/static in go1.19.
# static contains pprof trace viewer html javascript and markdown
install -d  %{buildroot}%{_datadir}/go/%{go_label}/src/cmd/trace/static
install -Dm644 src/cmd/trace/static/* %{buildroot}%{_datadir}/go/%{go_label}/src/cmd/trace/static
# pprof viewer html templates are needed for import runtime/pprof
install -d  %{buildroot}%{_datadir}/go/%{go_label}/src/cmd/vendor/github.com/google/pprof/internal/driver/html
install -Dm644 src/cmd/vendor/github.com/google/pprof/internal/driver/html/* %{buildroot}%{_datadir}/go/%{go_label}/src/cmd/vendor/github.com/google/pprof/internal/driver/html

mkdir -p $GOROOT/src
for i in $(ls %{buildroot}/usr/share/go/%{go_label}/src);do
  ln -s /usr/share/go/%{go_label}/src/$i $GOROOT/src/$i
done
# add lib files that are needed (such as the timezone database).
install -d $GOROOT/lib
find lib -type f -exec install -D -m644 {} $GOROOT/{} \;

# copy document templates, packages, obj libs and command utilities
mkdir -p $GOROOT/bin
# remove bootstrap
rm -rf pkg/bootstrap
cp -r pkg $GOROOT
cp bin/* $GOROOT/bin
# add wasm (Web Assembly) boo#1139210
mkdir -p $GOROOT/misc/wasm
cp misc/wasm/* $GOROOT/misc/wasm
rm -f %{buildroot}%{_bindir}/{hgpatch,quietgcc}

# gdbinit
mkdir -p $GOROOT/bin/gdbinit.d
echo "add-auto-load-safe-path /usr/%{_lib}/go/%{go_label}/src/runtime/runtime-gdb.py" > $GOROOT/bin/gdbinit.d/go.gdb
install -Dm644 $GOROOT/bin/gdbinit.d/go.gdb %{buildroot}%{_sysconfdir}/gdbinit.d/go.gdb

# go, gofmt
install -Dm755 $GOROOT/bin/go %{buildroot}%{_bindir}/go
install -m755 $GOROOT/bin/gofmt %{buildroot}%{_bindir}/gofmt

# documentation and examples
# fix documetation permissions (rpmlint warning)
find doc/ misc/ -type f -exec chmod 0644 '{}' +
# remove unwanted arch-dependant binaries (rpmlint warning)
rm -rf misc/cgo/test/{_*,*.o,*.out,*.6,*.8}
# prepare go-doc
mkdir -p %{buildroot}%{_docdir}/go/%{go_label}
cp -r CONTRIBUTING.md LICENSE PATENTS README.md %{buildroot}%{_docdir}/go/%{go_label}
cp -r doc/* %{buildroot}%{_docdir}/go/%{go_label}

%fdupes -s %{buildroot}%{_prefix}

popd # end of install

%files
%{_bindir}/go
%{_bindir}/gofmt
%dir %{_libdir}/go
%{_libdir}/go/%{go_label}
%dir %{_datadir}/go
%{_datadir}/go/%{go_label}
%dir %{_sysconfdir}/gdbinit.d/
%config %{_sysconfdir}/gdbinit.d/go.gdb
%dir %{_docdir}/go
%dir %{_docdir}/go/%{go_label}
%doc %{_docdir}/go/%{go_label}/CONTRIBUTING.md
%doc %{_docdir}/go/%{go_label}/PATENTS
%doc %{_docdir}/go/%{go_label}/README.md
%license %{_docdir}/go/%{go_label}/LICENSE

# We don't include TSAN in the main Go package.
%ifarch %{tsan_arch}
%exclude %{_datadir}/go/%{go_label}/src/runtime/race/race_linux_%{go_arch}.syso
%endif

# We don't include libstd.so in the main Go package.
%if %{with_shared}
# ./go/1.21/pkg/linux_amd64_dynlink/libstd.so
%exclude %{_libdir}/go/%{go_label}/pkg/linux_%{go_arch}_dynlink/libstd.so
%endif

%files doc
# SLE-12 SP5 rpm macro environment does not work with single glob {*.html,godebug.md}
%doc %{_docdir}/go/%{go_label}/*.html
%doc %{_docdir}/go/%{go_label}/godebug.md

%ifarch %{tsan_arch}
%files race
%{_datadir}/go/%{go_label}/src/runtime/race/race_linux_%{go_arch}.syso
%endif

%if %{with_shared}
%files libstd
%{_libdir}/go/%{go_label}/pkg/linux_%{go_arch}_dynlink/libstd.so
%endif

%changelog

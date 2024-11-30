#
# spec file for package go1.21
#
# Copyright (c) 2021 SUSE LLC
#
# All modifications and additions to the file contributed by third parties
# remain the property of their copyright owners, unless otherwise agreed
# upon. The license for this file, and modifications and additions to the
# file, is the same license as for the pristine package itself (unless the
# license for the pristine package is not an Open Source License, in which
# case the license is the MIT License). An "Open Source License" is a
# license that conforms to the Open Source Definition (Version 1.9)
# published by the Open Source Initiative.

# Please submit bugfixes or comments via https://bugs.opensuse.org/
#


# strip will cause Go's .a archives to become invalid because strip appears to
# reassemble the archive incorrectly. This is a known issue upstream
# (https://github.com/golang/go/issues/17890), but we have to deal with it in
# the meantime.
%undefine _build_create_debug
%define __arch_install_post export NO_BRP_STRIP_DEBUG=true NO_BRP_AR=true

%define gcc_go_version 13
%define go_bootstrap_version go1.18

# Always use gccgo
%bcond_without gccgo

# Build go-race only on platforms where it's supported (both amd64 and aarch64
# requires SLE15-or-later because of C++14, and ppc64le doesn't build at all
# on openSUSE yet).
%if 0
%define tsan_arch x86_64 aarch64 x390x ppc64le
%else
# Cannot use {nil} here (ifarch doesn't like it) so just make up a fake
# architecture that no build will ever match.
%define tsan_arch openSUSE_FAKE_ARCH
%endif

# Go has precompiled versions of LLVM's compiler-rt inside their source code.
# We cannot ship pre-compiled binaries so we have to recompile said source,
# however they vendor specific commits from upstream. This value comes from
# src/runtime/race/README (and we verify that it matches in check).
#
# In order to update the TSAN version, modify _service. See boo#1052528 for
# more details.
%define tsan_commit 6c75db8b4bc59eace18143ce086419d37da24746

%define go_api 1.21

# shared library support
%if "%{rpm_vercmp %{go_api} 1.5}" > "0"
%if %{with gccgo}
%define with_shared 1
%else
%ifarch %ix86 %arm x86_64 aarch64
%define with_shared 1
%else
%define with_shared 0
%endif
%endif
%else
%define with_shared 0
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
%endif
%ifarch aarch64
%define go_arch arm64
%endif
%ifarch %arm
%define go_arch arm
%endif
%ifarch ppc64
%define go_arch ppc64
%endif
%ifarch ppc64le
%define go_arch ppc64le
%endif
%ifarch s390x
%define go_arch s390x
%endif
%ifarch riscv64
%define go_arch riscv64
%endif

Name:           go1.21
Version:        1.21.13
Release:        1
Summary:        A compiled, garbage-collected, concurrent programming language
License:        BSD-3-Clause
Group:          Development/Languages/Go
URL:            https://github.com/sailfishos-mirror/go/
Source0:        %{name}-%{version}.tar.xz
Source1:        go-rpmlintrc
Source6:        go.gdbinit
# We have to compile TSAN ourselves. boo#1052528
Source100:      llvm-%{tsan_commit}.tar.xz
# PATCH-FIX-UPSTREAM prefer /etc/hosts over DNS when /etc/nsswitch.conf not present boo#1172868 gh#golang/go#35305
Patch13:        reproducible.patch

BuildRoot:      %{_tmppath}/%{name}-%{version}-build
# boostrap
%if %{with gccgo}
#BuildRequires:  binutils-gold
# FIXME when we have gcc 13
# BuildRequires:  gcc-go >= %%{gcc_go_version}
BuildRequires:  gcc-go
%else
# no gcc-go
BuildRequires:  %{go_bootstrap_version}
%endif
BuildRequires:  fdupes
Recommends:     %{name}-doc = %{version}
%ifarch %{tsan_arch}
# Needed to compile compiler-rt/TSAN.
BuildRequires:  gcc-c++
%endif
BuildRequires:  rpm >= 4.11.1
Requires:       gcc

BuildRequires:  git

# BusyBox xargs doesn't support '-d'
BuildRequires:  gnu-findutils

Provides:       go = %{version}
Provides:       go-devel = go%{version}
Provides:       go-devel-static = go%{version}
Provides:       golang(API) = %{go_api}
# We provide this for RH/Fedora compatibility
Provides:       golang = %{version}
Obsoletes:      go-devel < go%{version}
# go-vim/emacs were separate projects starting from 1.4
Obsoletes:      go-emacs <= 1.3.3
Obsoletes:      go-vim <= 1.3.3
ExclusiveArch:  %ix86 x86_64 %arm aarch64 ppc64 ppc64le s390x riscv64

%description
Go is an expressive, concurrent, garbage collected systems programming language
that is type safe and memory safe. It has pointers but no pointer arithmetic.
Go has fast builds, clean syntax, garbage collection, methods for any type, and
run-time reflection. It feels like a dynamic language but has the speed and
safety of a static language.

%package doc
Summary:        Go documentation
Group:          Documentation/Other
# We provide this for RH/Fedora compatibility
Provides:       golang-docs = %{version}
Requires:       %{name} = %{version}
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
# We provide this for RH/Fedora compatibility
Provides:       golang-race = %{version}

%description race
Go runtime race detector libraries. Install this package if you wish to use the
-race option, in order to detect race conditions present in your Go programs.
%endif

%prep
%ifarch %{tsan_arch}
# compiler-rt (from LLVM)
%setup -q -T -b 100 -n llvm-%{tsan_commit}
%endif
# go
%setup -q -n %{name}-%{version}
pushd go
%patch -P 13 -p1
popd

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
popd
cp -v "$TSAN_DIR/race_linux_%{go_arch}.syso" src/runtime/race/
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
export GOROOT="`pwd`"/go
export GOROOT_FINAL=%{_libdir}/go/%{go_api}
export GOBIN="$GOROOT/bin"
mkdir -p "$GOBIN"
cd "$GOROOT"/src
#HOST_EXTRA_CFLAGS="%%{optflags} -Wno-error" ./make.bash -v
HOST_EXTRA_CFLAGS="%{optflags} -Wno-error" taskset 0x1 ./make.bash -v

cd ../
%ifarch %{tsan_arch}
# Install TSAN-friendly version of the std libraries.
bin/go install -race std
%endif

%if %{with_shared}
bin/go install -buildmode=shared -linkshared std
%endif

%check
%ifarch %{tsan_arch}
# Make sure that we have the right TSAN checked out.
grep "^race_linux_%{go_arch}.syso built with LLVM %{tsan_commit}" src/runtime/race/README
%endif

%install
export GOROOT="%{buildroot}%{_libdir}/go/%{go_api}"

# locations for third party libraries, see README-openSUSE for info about locations.
install -d  %{buildroot}%{_datadir}/go/%{go_api}/contrib
install -d  $GOROOT/contrib/pkg/linux_%{go_arch}
ln -s %{_libdir}/go/%{go_api}/contrib/pkg/ %{buildroot}%{_datadir}/go/%{go_api}/contrib/pkg
install -d  %{buildroot}%{_datadir}/go/%{go_api}/contrib/cmd
install -d  %{buildroot}%{_datadir}/go/%{go_api}/contrib/src
ln -s %{_datadir}/go/%{go_api}/contrib/src/ %{buildroot}%{_libdir}/go/%{go_api}/contrib/src

# source files for go install, godoc, etc
install -d %{buildroot}%{_datadir}/go/%{go_api}
for ext in *.{go,c,h,s,S,py,syso}; do
  find src -name ${ext} -exec install -Dm644 \{\} %{buildroot}%{_datadir}/go/%{go_api}/\{\} \;
done
mkdir -p $GOROOT/src
for i in $(ls %{buildroot}/usr/share/go/%{go_api}/src);do
  ln -s /usr/share/go/%{go_api}/src/$i $GOROOT/src/$i
done
# add lib files that are needed (such as the timezone database).
install -d $GOROOT/lib
find lib -type f -exec install -D -m644 {} $GOROOT/{} \;

# copy document templates, packages, obj libs and command utilities
mkdir -p $GOROOT/bin
# remove bootstrap
rm -rf pkg/bootstrap
cp -r pkg $GOROOT
cp bin/* $GOROOT/bin/
mkdir -p $GOROOT/misc/trace
cp misc/trace/* $GOROOT/misc/trace
# add wasm (Web Assembly) boo#1139210
mkdir -p $GOROOT/misc/wasm
cp misc/wasm/* $GOROOT/misc/wasm
rm -f %{buildroot}%{_bindir}/{hgpatch,quietgcc}

# gdbinit
#install -Dm644 %{SOURCE6} $GOROOT/bin/gdbinit.d/go.gdb
#%if "%{_lib}" == "lib64"
#sed -i "s/lib/lib64/" $GOROOT/bin/gdbinit.d/go.gdb
#sed -i "s/\$go_api/%{go_api}/" $GOROOT/bin/gdbinit.d/go.gdb
#%endif

# documentation and examples
# fix documetation permissions (rpmlint warning)
find doc/ misc/ -type f -exec chmod 0644 '{}' +
# remove unwanted arch-dependant binaries (rpmlint warning)
rm -rf misc/cgo/test/{_*,*.o,*.out,*.6,*.8}
# prepare go-doc
mkdir -p %{buildroot}%{_docdir}/go/%{go_api}
cp -r AUTHORS CONTRIBUTORS CONTRIBUTING.md LICENSE PATENTS README.md %{buildroot}%{_docdir}/go/%{go_api}
cp -r doc/* %{buildroot}%{_docdir}/go/%{go_api}

%fdupes -s %{buildroot}%{_prefix}

%files
#%{_bindir}/go
#%{_bindir}/gofmt
%dir %{_libdir}/go
%{_libdir}/go/%{go_api}
%dir %{_datadir}/go
%{_datadir}/go/%{go_api}
#%dir %{_sysconfdir}/gdbinit.d/
#%config %{_sysconfdir}/gdbinit.d/go.gdb
#%ghost %{_sysconfdir}/alternatives/go
#%ghost %{_sysconfdir}/alternatives/gofmt
#%ghost %{_sysconfdir}/alternatives/go.gdb
%dir %{_docdir}/go
%dir %{_docdir}/go/%{go_api}
%doc %{_docdir}/go/%{go_api}/AUTHORS
%doc %{_docdir}/go/%{go_api}/CONTRIBUTORS
%doc %{_docdir}/go/%{go_api}/CONTRIBUTING.md
%doc %{_docdir}/go/%{go_api}/PATENTS
%doc %{_docdir}/go/%{go_api}/README.md
%if 0%{?suse_version} < 1500
%doc %{_docdir}/go/%{go_api}/LICENSE
%else
%license %{_docdir}/go/%{go_api}/LICENSE
%endif

# We don't include TSAN in the main Go package.
%ifarch %{tsan_arch}
%exclude %{_datadir}/go/%{go_api}/src/runtime/race/race_linux_%{go_arch}.syso
%endif

%files doc
%defattr(-,root,root,-)
%doc %{_docdir}/go/%{go_api}/codewalk
%doc %{_docdir}/go/%{go_api}/articles
%doc %{_docdir}/go/%{go_api}/progs
%doc %{_docdir}/go/%{go_api}/play
%doc %{_docdir}/go/%{go_api}/gopher
%doc %{_docdir}/go/%{go_api}/*.html
%doc %{_docdir}/go/%{go_api}/*.css
%doc %{_docdir}/go/%{go_api}/*.png

%ifarch %{tsan_arch}
%files race
%{_datadir}/go/%{go_api}/src/runtime/race/race_linux_%{go_arch}.syso
%endif


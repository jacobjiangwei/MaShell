# Homebrew Formula for MaShell
# This file is auto-updated by GitHub Actions on each release.
# 
# To install: brew install your-username/tap/mashell
# 
# Manual setup:
# 1. Create a repo: github.com/your-username/homebrew-tap
# 2. Add this formula as: Formula/mashell.rb
# 3. Users can then: brew tap your-username/tap && brew install mashell

class Mashell < Formula
  include Language::Python::Virtualenv

  desc "AI-powered command line assistant"
  homepage "https://github.com/jacobjiangwei/MaShell"
  url "https://github.com/jacobjiangwei/MaShell/archive/refs/tags/v__VERSION__.tar.gz"
  sha256 "__SHA256__"
  license "GPL-3.0"

  depends_on "python@3.11"

  # Dependencies are installed via pip from pyproject.toml
  # Using system_site_packages to leverage pre-installed packages

  def install
    # Install using pip which reads dependencies from pyproject.toml
    virtualenv_create(libexec, "python3.11")
    system libexec/"bin/pip", "install", "--no-deps", "."
    # Install dependencies
    system libexec/"bin/pip", "install", "httpx>=0.25.0", "rich>=13.0.0", "pyyaml>=6.0", "prompt-toolkit>=3.0"
    bin.install_symlink libexec/"bin/mashell"
  end

  test do
    assert_match "MaShell", shell_output("#{bin}/mashell --help")
  end
end

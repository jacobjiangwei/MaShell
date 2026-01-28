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
  homepage "https://github.com/your-username/MaShell"
  url "https://github.com/your-username/MaShell/archive/refs/tags/v0.1.0.tar.gz"
  sha256 "PLACEHOLDER_SHA256"
  license "GPL-3.0"

  depends_on "python@3.11"

  resource "httpx" do
    url "https://files.pythonhosted.org/packages/source/h/httpx/httpx-0.27.0.tar.gz"
    sha256 "PLACEHOLDER"
  end

  resource "rich" do
    url "https://files.pythonhosted.org/packages/source/r/rich/rich-13.7.0.tar.gz"
    sha256 "PLACEHOLDER"
  end

  resource "pyyaml" do
    url "https://files.pythonhosted.org/packages/source/p/pyyaml/PyYAML-6.0.1.tar.gz"
    sha256 "PLACEHOLDER"
  end

  resource "prompt-toolkit" do
    url "https://files.pythonhosted.org/packages/source/p/prompt_toolkit/prompt_toolkit-3.0.43.tar.gz"
    sha256 "PLACEHOLDER"
  end

  def install
    virtualenv_install_with_resources
  end

  test do
    assert_match "MaShell", shell_output("#{bin}/mashell --help 2>&1", 1)
  end
end

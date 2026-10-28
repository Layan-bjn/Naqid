// Naqid Frontend Application Logic
document.addEventListener("DOMContentLoaded", () => {
  const auditForm = document.getElementById("audit-form");
  const urlInput = document.getElementById("url-input");
  const startBtn = document.getElementById("start-audit-btn");
  const demoBtn = document.getElementById("demo-btn");
  
  const progressContainer = document.getElementById("progress-container");
  const progressPhaseTitle = document.getElementById("progress-phase-title");
  const errorBanner = document.getElementById("error-banner");
  const errorMessage = document.getElementById("error-message");
  
  const resultsSection = document.getElementById("results-section");
  const scoreNumber = document.getElementById("score-number");
  const scoreRingProgress = document.getElementById("score-ring-progress");
  const scoreGradeText = document.getElementById("score-grade-text");
  const scoreEvaluationText = document.getElementById("score-evaluation-text");
  const summaryText = document.getElementById("summary-text");
  const auditDuration = document.getElementById("audit-duration");

  const countCritical = document.getElementById("count-critical");
  const countHigh = document.getElementById("count-high");
  const countMedium = document.getElementById("count-medium");
  const countLow = document.getElementById("count-low");
  const totalIssuesCount = document.getElementById("total-issues-count");

  const desktopImg = document.getElementById("desktop-img");
  const mobileImg = document.getElementById("mobile-img");

  const filterSeverity = document.getElementById("filter-severity");
  const filterCategory = document.getElementById("filter-category");
  const issuesList = document.getElementById("issues-list");
  const exportJsonBtn = document.getElementById("export-json-btn");

  const apiStatusPill = document.getElementById("api-status-pill");
  const apiStatusText = document.getElementById("api-status-text");

  let currentReport = null;
  let progressInterval = null;

  const CATEGORY_NAMES = {
    layout: "تخطيط (Layout)",
    visual: "بصري (Visual)",
    responsive: "تجاوب (Responsive)",
    accessibility: "إمكانية الوصول (A11y)",
    functional: "وظيفي (Functional)",
    ux: "تجربة مستخدم (UX)"
  };

  const SEVERITY_NAMES = {
    critical: "حرجة",
    high: "عالية",
    medium: "متوسطة",
    low: "منخفضة"
  };

  // 1. Check API Health
  async function checkHealth() {
    try {
      const res = await fetch("/api/health");
      if (res.ok) {
        const data = await res.json();
        apiStatusPill.className = "status-pill " + (data.has_gemini_key ? "status-online" : "status-demo");
        apiStatusText.textContent = data.has_gemini_key 
          ? `Gemini متصل (${data.model})` 
          : "الوضع التجريبي النشط (جاهز للتدقيق)";
      } else {
        throw new Error();
      }
    } catch {
      apiStatusPill.className = "status-pill status-offline";
      apiStatusText.textContent = "الخادم غير متصل";
    }
  }
  checkHealth();

  // 2. Demo Page Quick Action
  demoBtn.addEventListener("click", () => {
    const demoUrl = `${window.location.origin}/demo/broken_page.html`;
    urlInput.value = demoUrl;
    const isDemoChecked = document.getElementById("demo-mode-checkbox") ? document.getElementById("demo-mode-checkbox").checked : false;
    runAudit(demoUrl, isDemoChecked);
  });

  // 3. Form Submit
  auditForm.addEventListener("submit", (e) => {
    e.preventDefault();
    const url = urlInput.value.trim();
    if (!url) return;
    const isDemoChecked = document.getElementById("demo-mode-checkbox") ? document.getElementById("demo-mode-checkbox").checked : false;
    runAudit(url, isDemoChecked);
  });

  // 4. Run Audit
  async function runAudit(url, forceDemo) {
    showProgress();
    hideError();
    resultsSection.classList.add("hidden");
    startBtn.disabled = true;
    demoBtn.disabled = true;

    try {
      const response = await fetch("/api/audit", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: url, demo: forceDemo })
      });

      if (!response.ok) {
        let errDetail = "تعذر إتمام الفحص";
        try {
          const errData = await response.json();
          errDetail = errData.detail || errDetail;
        } catch (_) {}
        throw new Error(errDetail);
      }

      const report = await response.json();
      currentReport = report;
      finishProgress();
      renderReport(report);
    } catch (err) {
      clearInterval(progressInterval);
      progressContainer.classList.add("hidden");
      showError(err.message || "حدث خطأ أثناء إجراء الفحص.");
    } finally {
      startBtn.disabled = false;
      demoBtn.disabled = false;
    }
  }

  // 5. Progress Stepper Simulation
  function showProgress() {
    progressContainer.classList.remove("hidden");
    const steps = [
      document.getElementById("step-1"),
      document.getElementById("step-2"),
      document.getElementById("step-3"),
      document.getElementById("step-4")
    ];

    steps.forEach(s => {
      s.className = "step-item";
    });

    let currentStep = 0;
    progressPhaseTitle.textContent = "فتح الصفحة وتجهيز المتصفح...";
    steps[0].classList.add("active");

    clearInterval(progressInterval);
    progressInterval = setInterval(() => {
      if (currentStep < 3) {
        steps[currentStep].classList.remove("active");
        steps[currentStep].classList.add("completed");
        currentStep++;
        steps[currentStep].classList.add("active");

        if (currentStep === 1) {
          progressPhaseTitle.textContent = "التقاط لقطات الشاشة وفحص DOM...";
        } else if (currentStep === 2) {
          progressPhaseTitle.textContent = "تحليل الواجهة بالذكاء الاصطناعي البصري...";
        } else if (currentStep === 3) {
          progressPhaseTitle.textContent = "توليد التقرير وكود الإصلاح واختبارات Playwright...";
        }
      }
    }, 1800);
  }

  function finishProgress() {
    clearInterval(progressInterval);
    for (let i = 1; i <= 4; i++) {
      const s = document.getElementById(`step-${i}`);
      s.className = "step-item completed";
    }
    progressPhaseTitle.textContent = "اكتمل الفحص بنجاح!";
    setTimeout(() => {
      progressContainer.classList.add("hidden");
    }, 600);
  }

  function showError(msg) {
    errorMessage.textContent = msg;
    errorBanner.classList.remove("hidden");
  }

  function hideError() {
    errorBanner.classList.add("hidden");
  }

  // 6. Render Report
  function renderReport(report) {
    resultsSection.classList.remove("hidden");

    // Animate Score
    const score = report.score || 0;
    scoreNumber.textContent = score;
    const circumference = 2 * Math.PI * 50; // r=50 => ~314.16
    const offset = circumference - (score / 100) * circumference;
    scoreRingProgress.style.strokeDasharray = circumference;
    scoreRingProgress.style.strokeDashoffset = offset;

    if (score >= 80) {
      scoreRingProgress.style.stroke = "#10b981";
      scoreGradeText.textContent = "واجهة ممتازة";
      scoreEvaluationText.textContent = "الموقع يلتزم بأعلى معايير التجاوب وسهولة الاستخدام.";
    } else if (score >= 60) {
      scoreRingProgress.style.stroke = "#eab308";
      scoreGradeText.textContent = "جودة مقبولة بحاجة لتحسين";
      scoreEvaluationText.textContent = "توجد بعض الأخطاء البصرية والتجاوبية التي يفضل إصلاحها.";
    } else {
      scoreRingProgress.style.stroke = "#ef4444";
      scoreGradeText.textContent = "واجهة حرجة وبحاجة لتدخل";
      scoreEvaluationText.textContent = "تم اكتشاف عيوب جسيمة في التجاوب أو التصميم أو إمكانية الوصول.";
    }

    // Summary & Duration
    summaryText.textContent = report.summary || "لا يوجد ملخص متاح.";
    auditDuration.textContent = `⏱️ استغرق الفحص: ${report.duration_seconds} ثانية`;

    // Render Mode Badge (Live vs Cached)
    const modeBadge = document.getElementById("audit-mode-badge");
    if (modeBadge) {
      if (report.is_live) {
        modeBadge.className = "mode-badge badge-live";
        modeBadge.textContent = "● فحص حي";
      } else {
        modeBadge.className = "mode-badge badge-cached";
        modeBadge.textContent = "● نتيجة محفوظة";
      }
    }

    // Counters
    const issues = report.issues || [];
    totalIssuesCount.textContent = issues.length;

    let crit = 0, hi = 0, med = 0, lo = 0;
    issues.forEach(iss => {
      if (iss.severity === "critical") crit++;
      else if (iss.severity === "high") hi++;
      else if (iss.severity === "medium") med++;
      else if (iss.severity === "low") lo++;
    });

    countCritical.textContent = crit;
    countHigh.textContent = hi;
    countMedium.textContent = med;
    countLow.textContent = lo;

    // Screenshots
    if (report.screenshots) {
      desktopImg.src = report.screenshots.desktop || "";
      mobileImg.src = report.screenshots.mobile || "";
    }

    // Render Issues List
    renderIssuesList(issues);

    // Scroll to results
    resultsSection.scrollIntoView({ behavior: "smooth" });
  }

  // 7. Filter and Render Issues
  function renderIssuesList(issues) {
    issuesList.innerHTML = "";
    const sevVal = filterSeverity.value;
    const catVal = filterCategory.value;

    const filtered = issues.filter(iss => {
      const matchSev = sevVal === "all" || iss.severity === sevVal;
      const matchCat = catVal === "all" || iss.category === catVal;
      return matchSev && matchCat;
    });

    if (filtered.length === 0) {
      issuesList.innerHTML = `
        <div style="text-align: center; padding: 3rem; color: #94a3b8; background: var(--bg-card); border-radius: var(--radius-lg); border: 1px solid var(--border-color);">
          <p style="font-size: 1.1rem; font-weight: 600;">لا توجد مشكلات مطابقة لخيارات التصفية المحددة.</p>
        </div>
      `;
      return;
    }

    filtered.forEach((issue, index) => {
      const card = document.createElement("div");
      card.className = "issue-card";

      const catArabic = CATEGORY_NAMES[issue.category] || issue.category;
      const sevArabic = SEVERITY_NAMES[issue.severity] || issue.severity;
      const viewportText = issue.viewport === "both" ? "شامل (Desktop + Mobile)" : (issue.viewport === "mobile" ? "جوال (Mobile)" : "حاسوب (Desktop)");

      const fixCode = issue.suggested_fix ? (issue.suggested_fix.code || "") : "";
      const fixLang = issue.suggested_fix ? (issue.suggested_fix.language || "css") : "css";
      const fixExplanation = issue.suggested_fix ? (issue.suggested_fix.explanation || "") : "";
      const testCode = issue.test_scenario || "";

      card.innerHTML = `
        <div class="issue-card-top">
          <div class="issue-title-area">
            <span class="badge badge-${issue.severity}">${sevArabic}</span>
            <span class="badge badge-category">${catArabic}</span>
            <span class="badge badge-viewport">${viewportText}</span>
            <h4 class="issue-title">${escapeHtml(issue.title)}</h4>
          </div>
        </div>

        <div class="issue-location">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"></path>
            <circle cx="12" cy="10" r="3"></circle>
          </svg>
          <span>الموقع: ${escapeHtml(issue.location)}</span>
        </div>

        <p class="issue-description">${escapeHtml(issue.description)}</p>

        <!-- Suggested Fix Collapsible -->
        <details class="collapsible-box">
          <summary>
            <span>💡 كود الإصلاح المقترح</span>
            <span>▼</span>
          </summary>
          <div class="collapsible-content">
            <div class="code-header">
              <span class="code-lang-tag">${fixLang}</span>
              <button class="btn-copy" onclick="copyCode(this, \`${escapeJsString(fixCode)}\`)">نسخ الكود</button>
            </div>
            <pre class="code-block"><code>${escapeHtml(fixCode)}</code></pre>
            ${fixExplanation ? `<p class="fix-explanation">${escapeHtml(fixExplanation)}</p>` : ''}
          </div>
        </details>

        <!-- Playwright Test Scenario Collapsible -->
        <details class="collapsible-box">
          <summary>
            <span>🧪 سيناريو الفحص التلقائي (Playwright)</span>
            <span>▼</span>
          </summary>
          <div class="collapsible-content">
            <div class="code-header">
              <span class="code-lang-tag">python / playwright</span>
              <button class="btn-copy" onclick="copyCode(this, \`${escapeJsString(testCode)}\`)">نسخ الكود</button>
            </div>
            <pre class="code-block"><code>${escapeHtml(testCode)}</code></pre>
          </div>
        </details>
      `;

      issuesList.appendChild(card);
    });
  }

  // Filter Listeners
  filterSeverity.addEventListener("change", () => {
    if (currentReport) renderIssuesList(currentReport.issues || []);
  });
  filterCategory.addEventListener("change", () => {
    if (currentReport) renderIssuesList(currentReport.issues || []);
  });

  // Clicking severity counters triggers quick filter
  document.querySelectorAll(".counter-chip").forEach(chip => {
    chip.addEventListener("click", () => {
      const targetSev = chip.getAttribute("data-severity");
      filterSeverity.value = targetSev;
      if (currentReport) renderIssuesList(currentReport.issues || []);
    });
  });

  // 8. Screenshot Tabs
  document.querySelectorAll(".tab-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
      document.querySelectorAll(".tab-pane").forEach(p => p.classList.remove("active"));

      btn.classList.add("active");
      const targetId = btn.getAttribute("data-tab");
      const targetPane = document.getElementById(targetId);
      if (targetPane) targetPane.classList.add("active");
    });
  });

  // 9. Export Report JSON
  exportJsonBtn.addEventListener("click", () => {
    if (!currentReport) return;
    const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(currentReport, null, 2));
    const downloadAnchor = document.createElement("a");
    downloadAnchor.setAttribute("href", dataStr);
    downloadAnchor.setAttribute("download", `naqid-audit-report-${Date.now()}.json`);
    document.body.appendChild(downloadAnchor);
    downloadAnchor.click();
    downloadAnchor.remove();
  });

  // Utilities
  function escapeHtml(str) {
    if (!str) return "";
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function escapeJsString(str) {
    if (!str) return "";
    return String(str)
      .replace(/\\/g, "\\\\")
      .replace(/`/g, "\\`")
      .replace(/\$/g, "\\$");
  }

  // Global copy code helper
  window.copyCode = function(button, codeText) {
    navigator.clipboard.writeText(codeText).then(() => {
      const origText = button.textContent;
      button.textContent = "تم النسخ! ✓";
      button.style.color = "#10b981";
      setTimeout(() => {
        button.textContent = origText;
        button.style.color = "";
      }, 2000);
    }).catch(() => {
      button.textContent = "فشل النسخ";
    });
  };
});

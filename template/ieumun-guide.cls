%% IEUMUN 2026 Study Guide document class
\NeedsTeXFormat{LaTeX2e}
\ProvidesClass{ieumun-guide}[2026/09/29 v2 IEUMUN study guide]

\LoadClass[11pt,a4paper,oneside]{article}

\RequirePackage{iftex}
\RequireLuaTeX
\RequirePackage{etoolbox}
\RequirePackage{calc}
\RequirePackage{xcolor}
\RequirePackage[spanish.noshorthands,english]{babel}
\RequirePackage[autostyle]{csquotes}
\RequirePackage{fontspec}
% The top 150/1080 of the page width (2.92 cm on A4) holds the cover banner;
% the running header sits just below it.
\RequirePackage[
  a4paper,
  top=4.55cm,
  bottom=2.3cm,
  left=2.1cm,
  right=2.1cm,
  headheight=18pt,
  headsep=0.85cm,
  footskip=1.2cm,
]{geometry}
\RequirePackage{graphicx}
\RequirePackage[protrusion=true,expansion=true,tracking=true]{microtype}
\RequirePackage{ragged2e}
\RequirePackage{enumitem}
\RequirePackage{fancyhdr}
\RequirePackage{titlesec}
\RequirePackage{titletoc}
\RequirePackage[most]{tcolorbox}
\RequirePackage{caption}
\RequirePackage{needspace}
\RequirePackage{float}
\RequirePackage{tabularx}
\RequirePackage{booktabs}
\RequirePackage{xurl}

%% ---------------------------------------------------------------------------
%% Typography: Montserrat everywhere (static OTFs shipped with TeX Live)
%% ---------------------------------------------------------------------------
\defaultfontfeatures{Ligatures=TeX}
\setmainfont{Montserrat}[
  Extension      = .otf,
  UprightFont    = *-Regular,
  BoldFont       = *-SemiBold,
  ItalicFont     = *-Italic,
  BoldItalicFont = *-SemiBoldItalic,
  Numbers        = Proportional,
]
\setsansfont{Montserrat}[
  Extension      = .otf,
  UprightFont    = *-Regular,
  BoldFont       = *-SemiBold,
  ItalicFont     = *-Italic,
  BoldItalicFont = *-SemiBoldItalic,
]
\setmonofont{JetBrainsMono-Regular.otf}[Scale=0.85]

\newfontfamily\ieumun@light{Montserrat-Light.otf}
\newfontfamily\ieumun@medium{Montserrat-Medium.otf}
\newfontfamily\ieumun@semibold{Montserrat-SemiBold.otf}
\newfontfamily\ieumun@bold{Montserrat-Bold.otf}
\newfontfamily\ieumun@display{Montserrat-Bold.otf}[LetterSpace=-2.5]
\newfontfamily\ieumun@heavy{Montserrat-Black.otf}[LetterSpace=-3]
\newfontfamily\ieumun@thin{Montserrat-ExtraLight.otf}[LetterSpace=-2]
\newfontfamily\ieumun@label{Montserrat-SemiBold.otf}[LetterSpace=14]

% Leading is held in lengths so the short-page fixer can tighten it.
\newlength{\ieumun@lead}\setlength{\ieumun@lead}{17pt}
\newlength{\ieumun@letterlead}\setlength{\ieumun@letterlead}{18.5pt}
\newlength{\ieumun@footlead}\setlength{\ieumun@footlead}{12pt}
\renewcommand{\normalsize}{%
  \@setfontsize\normalsize{11}{\the\ieumun@lead}%
  \abovedisplayskip 10pt plus 2pt minus 4pt
  \belowdisplayskip \abovedisplayskip
}
\renewcommand{\small}{\@setfontsize\small{10}{15}}
\renewcommand{\footnotesize}{\@setfontsize\footnotesize{8.5}{\the\ieumun@footlead}}
\normalsize

% Justified text: a clean block, with hyphenation kept rare.
\setlength{\parindent}{0pt}
\setlength{\parskip}{0.75em plus 0.2em minus 0.1em}
\tolerance=600
\pretolerance=300
\setlength{\emergencystretch}{1.5em}
\hyphenpenalty=300
\exhyphenpenalty=300
\doublehyphendemerits=900000
\finalhyphendemerits=500000
\adjdemerits=10000

% No lone first/last line of a paragraph on a page, no page break at a hyphen.
\clubpenalty=10000
\widowpenalty=10000
\displaywidowpenalty=10000
\brokenpenalty=10000

%% ---------------------------------------------------------------------------
%% Colour system: three shared category accents
%% ---------------------------------------------------------------------------
\definecolor{ieumun@text}{HTML}{1D1D1F}
\definecolor{ieumun@secondary}{HTML}{6E6E73}
\definecolor{ieumun@tertiary}{HTML}{86868B}
\definecolor{ieumun@hairline}{HTML}{D2D2D7}
\definecolor{ieumun@surface}{HTML}{F5F5F7}

\definecolor{ieumun@cat@black}{HTML}{000000}
\definecolor{ieumun@cat@red}{HTML}{DA1420}
\definecolor{ieumun@cat@blue}{HTML}{000153}

\colorlet{ieumun@accent}{ieumun@cat@black}
\colorlet{ieumun@link}{ieumun@text}
\colorlet{ieumun@coveraccent}{white}

\def\ieumun@catok@black{}
\def\ieumun@catok@red{}
\def\ieumun@catok@blue{}
\newcommand{\guidecategory}[1]{%
  \ifcsname ieumun@catok@#1\endcsname
    \colorlet{ieumun@accent}{ieumun@cat@#1}%
  \else
    \ClassError{ieumun-guide}{Unknown category `#1'}{Use black, red, or blue.}%
  \fi
  \colorlet{ieumun@link}{ieumun@cat@#1}%
  % Black and navy vanish on the dark cover artwork, so only red shows there.
  \ifstrequal{#1}{red}{%
    \colorlet{ieumun@coveraccent}{ieumun@cat@red}%
  }{%
    \colorlet{ieumun@coveraccent}{white}%
  }%
}
\newcommand{\guideaccent}[1]{%
  \definecolor{ieumun@accent}{HTML}{#1}%
  \colorlet{ieumun@link}{ieumun@accent}%
  \colorlet{ieumun@coveraccent}{ieumun@accent}%
}

\AtBeginDocument{\pagecolor{white}\color{ieumun@text}}

%% ---------------------------------------------------------------------------
%% Metadata
%% ---------------------------------------------------------------------------
\newcommand{\ieumun@committee}{}
\newcommand{\ieumun@longname}{}
\newcommand{\ieumun@topic}{}
\newcommand{\ieumun@authors}{}
\newcommand{\ieumun@editor}{}
\newcommand{\ieumun@cover}{}
\newcommand{\ieumun@conference}{IEUMUN 2026}
\newcommand{\guidecommittee}[1]{\renewcommand{\ieumun@committee}{#1}}
\newcommand{\guidelongname}[1]{\renewcommand{\ieumun@longname}{#1}}
\newcommand{\guidetopic}[1]{\renewcommand{\ieumun@topic}{#1}}
\newcommand{\guideauthors}[1]{\renewcommand{\ieumun@authors}{#1}}
\newcommand{\guideeditor}[1]{\renewcommand{\ieumun@editor}{#1}}
\newcommand{\guidecover}[1]{\renewcommand{\ieumun@cover}{#1}}
\newcommand{\guideconference}[1]{\renewcommand{\ieumun@conference}{#1}}

% Fixed wording, switchable per guide language.
\newcommand{\ieumun@lbl@contents}{Contents}
\newcommand{\ieumun@lbl@letter}{A letter from}
\newcommand{\ieumun@lbl@studyguide}{Study Guide}
\newcommand{\ieumun@lbl@writtenby}{Written by}
\newcommand{\ieumun@lbl@editedby}{Edited by}
\newcommand{\ieumun@lbl@references}{References}
\newcommand{\guideauthorslabel}[1]{\renewcommand{\ieumun@lbl@writtenby}{#1}}
\newcommand{\guideeditorlabel}[1]{\renewcommand{\ieumun@lbl@editedby}{#1}}
\newcommand{\guidelanguage}[1]{%
  \ifstrequal{#1}{spanish}{%
    \renewcommand{\ieumun@lbl@contents}{Índice}%
    \renewcommand{\ieumun@lbl@letter}{Una carta de}%
    \renewcommand{\ieumun@lbl@studyguide}{Guía de estudio}%
    \renewcommand{\ieumun@lbl@writtenby}{Escrito por}%
    \renewcommand{\ieumun@lbl@editedby}{Editado por}%
    \renewcommand{\ieumun@lbl@references}{Referencias}%
  }{}%
  \AtBeginDocument{\selectlanguage{#1}}%
}

%% ---------------------------------------------------------------------------
%% References: APA 7 via biblatex + biber
%% ---------------------------------------------------------------------------
\RequirePackage[
  backend=biber,
  style=apa,
  sortcites=false,
  uniquename=false,
]{biblatex}

\setlength{\bibhang}{1.6em}
\setlength{\bibitemsep}{0.7em}
\newcommand{\ieumun@bibfont}{\fontsize{9.5}{14}\selectfont}
\renewcommand*{\bibfont}{\ieumun@bibfont}
\appto{\bibsetup}{\RaggedRight}
% URLs break without stretchable gaps ("www . example"), since text is ragged.
\biburlbigskip=0mu
\biburlnumskip=0mu
\biburlucskip=0mu
\biburllcskip=0mu

% \source[postnote]{key1,key2}: footnote with the full APA reference the
% first time a work is cited and "Author (Year), Title" afterwards.
\newif\ifieumun@firstsrc
\newif\ifieumun@lastshort
\newcommand{\ieumun@onesource}[1]{%
  \ifieumun@firstsrc\global\ieumun@firstsrcfalse\else; \fi
  \ifcsname ieumun@seen@#1\endcsname
    \citeauthor{#1} (\citeyear{#1}), \citetitle{#1}%
    \global\ieumun@lastshorttrue
  \else
    \fullcite{#1}\ieumun@fullstop{#1}%
    \global\expandafter\let\csname ieumun@seen@#1\endcsname\relax
    \global\ieumun@lastshortfalse
  \fi
}
% APA: full references end with a period unless they end with a URL or DOI.
\DeclareCiteCommand{\ieumun@fullstop}
  {}
  {\iffieldundef{doi}{\iffieldundef{url}{.}{}}{}}
  {}
  {}
\newcommand{\source}[2][]{%
  \footnote{%
    \global\ieumun@firstsrctrue
    \forcsvlist{\ieumun@onesource}{#2}%
    \ifblank{#1}{\ifieumun@lastshort.\fi}{, #1.}%
  }%
}

\RequirePackage{hyperref}
\hypersetup{
  colorlinks=true,
  linkcolor=ieumun@text,
  citecolor=ieumun@secondary,
  urlcolor=ieumun@link,
  pdfcreator={IEUMUN 2026 study guide template},
}
\urlstyle{same}
\AtBeginDocument{%
  \hypersetup{
    pdftitle={\ieumun@committee{} -- \ieumun@topic},
    pdfauthor={\ieumun@authors},
  }%
}

%% ---------------------------------------------------------------------------
%% Page furniture
%% ---------------------------------------------------------------------------
\newcommand{\ieumun@kicker}[1]{%
  {\ieumun@label\fontsize{7.5}{9}\selectfont\MakeUppercase{#1}}%
}

\pagestyle{fancy}
\fancyhf{}
\renewcommand{\headrulewidth}{0pt}
\renewcommand{\footrulewidth}{0pt}
\fancyhead[L]{%
  \ieumun@kicker{\ieumun@conference}%
  \hspace{0.6em}{\color{ieumun@hairline}\rule[-0.1em]{0.4pt}{0.9em}}\hspace{0.6em}%
  {\color{ieumun@secondary}\ieumun@kicker{\ieumun@committee}}%
}
\fancyhead[R]{%
  {\color{ieumun@secondary}\ieumun@medium\fontsize{8}{10}\selectfont\leftmark}%
}
\fancyfoot[L]{%
  {\color{ieumun@tertiary}\ieumun@medium\fontsize{8}{10}\selectfont\ieumun@lbl@studyguide}%
}
\fancyfoot[R]{%
  {\ieumun@semibold\fontsize{9}{10}\selectfont\color{ieumun@accent}\thepage}%
}
\fancypagestyle{plain}{%
  \fancyhf{}%
  \fancyfoot[R]{%
    {\ieumun@semibold\fontsize{9}{10}\selectfont\color{ieumun@accent}\thepage}%
  }%
}
\renewcommand{\sectionmark}[1]{\markboth{#1}{}}
\renewcommand{\subsectionmark}[1]{}

% Banner: the bottom strip of the cover artwork, in a 1080 x 150 proportion,
% full-bleed across the top of every page after the cover.
\newsavebox{\ieumun@coverbox}
\newsavebox{\ieumun@bannerbox}
\newlength{\ieumun@bannerheight}
\newlength{\ieumun@trimtop}
\AtBeginDocument{%
  \setlength{\ieumun@bannerheight}{\dimexpr\paperwidth*150/1080\relax}%
  \IfFileExists{\ieumun@cover}{%
    \sbox{\ieumun@coverbox}{\includegraphics{\ieumun@cover}}%
    \setlength{\ieumun@trimtop}{%
      \dimexpr\ht\ieumun@coverbox-\wd\ieumun@coverbox*150/1080\relax}%
    \sbox{\ieumun@bannerbox}{%
      \includegraphics[trim=0 0 0 {\the\ieumun@trimtop}, clip,
        width=\paperwidth, height=\ieumun@bannerheight]{\ieumun@cover}}%
  }{}%
}
\AddToHook{shipout/background}{%
  \ifnum\value{page}>1
    \put(0pt,-\ieumun@bannerheight){\usebox{\ieumun@bannerbox}}%
  \fi
}

%% ---------------------------------------------------------------------------
%% Headings: every section opens a fresh page, magazine style
%% ---------------------------------------------------------------------------
\setcounter{secnumdepth}{1}
\setcounter{tocdepth}{2}
\renewcommand{\thesection}{\two@digits{\value{section}}}

% Short-page fixer. Each section ("block") records whether its last page holds
% only a few lines. On the next run that block is set tighter, one level per
% run, until the stragglers move back:
%   1: every paragraph is set one line shorter where the spacing allows
%   2: + slightly tighter leading
%   3: + tighter paragraph and footnote spacing
%   4: + the section's pages hold one more line (footer stays in place)
%   5: + two more lines
%   6: + a more compact section opening (smaller number, less space)
% Levels 3+ also tighten reference lists. Levels never go down, so the layout
% converges; latexmk reruns until stable.
\newcommand{\ieumun@maxlevel}{6}
\newif\ifieumun@compacthead
\newlength{\ieumun@basetextheight}
\newlength{\ieumun@basefootskip}
\AtBeginDocument{%
  \setlength{\ieumun@basetextheight}{\textheight}%
  \setlength{\ieumun@basefootskip}{\footskip}%
}
\newcounter{ieumun@block}
\newcommand{\ieumun@blockstart}{0}
\newif\ifieumun@loosen
\newlength{\ieumun@shortpage}
\AtBeginDocument{\setlength{\ieumun@shortpage}{0.3\textheight}}
\newcommand{\ieumun@savelevel}[2]{\expandafter\xdef\csname ieumun@level@#1\endcsname{#2}}
\newcommand{\ieumun@level}[1]{%
  \ifcsname ieumun@level@#1\endcsname\csname ieumun@level@#1\endcsname\else 0\fi}
\AddToHook{para/begin}{\ifieumun@loosen\looseness=-1\fi}

% Assignments are global because titlesec runs \sectionbreak inside a group.
\newcommand{\ieumun@applylevel}[1]{%
  \ifnum#1>0
    \global\ieumun@loosentrue\global\tolerance=1200
  \else
    \global\ieumun@loosenfalse\global\tolerance=600
  \fi
  \global\ieumun@lead=17pt
  \global\ieumun@letterlead=18.5pt
  \global\ieumun@footlead=12pt
  \global\parskip=0.75em plus 0.2em minus 0.1em
  \gdef\ieumun@leadfont{\fontsize{15}{23}}%
  \global\bibitemsep=0.7em
  \gdef\ieumun@bibfont{\fontsize{9.5}{14}\selectfont}%
  \ifnum#1>2 \global\bibitemsep=0.4em \fi
  \ifnum#1>5
    \global\ieumun@compactheadtrue
    \global\bibitemsep=0.25em
    \gdef\ieumun@bibfont{\fontsize{9.5}{12.5}\selectfont}%
  \else
    \global\ieumun@compactheadfalse
  \fi
  \ifcase#1\relax
  \or
    \global\parskip=0.7em plus 0.2em minus 0.15em
  \or
    \global\ieumun@lead=16.3pt
    \global\ieumun@letterlead=17.6pt
    \global\parskip=0.6em plus 0.2em minus 0.15em
  \else
    \global\ieumun@lead=15.8pt
    \global\ieumun@letterlead=17pt
    \global\ieumun@footlead=11pt
    \global\parskip=0.5em plus 0.15em minus 0.15em
    \gdef\ieumun@leadfont{\fontsize{13.5}{20}}%
  \fi
  \global\baselineskip=\ieumun@lead
  \global\normalbaselineskip=\ieumun@lead
  % Levels 4-5: taller text area, with the footer pulled up by the same amount
  % so it stays at the same spot on the page.
  \global\textheight=\ieumun@basetextheight
  \global\footskip=\ieumun@basefootskip
  \ifnum#1>3
    \global\advance\textheight by \dimexpr\ieumun@lead*(\ifnum#1>5 5\else#1\fi-3)\relax
    \global\advance\footskip by -\dimexpr\ieumun@lead*(\ifnum#1>5 5\else#1\fi-3)\relax
  \fi
  \global\vsize=\textheight
  \global\@colht=\textheight
  \global\@colroom=\textheight
}

\newcommand{\ieumun@closeblock}{%
  % A feasible breakpoint makes TeX decide whether the current page is already
  % overfull (e.g. pushed by footnotes), so \pagetotal and the page number
  % below describe the section's real last page.
  \par\penalty\z@
  \ifnum\value{ieumun@block}>0
    \edef\ieumun@current{\ieumun@level{\the\value{ieumun@block}}}%
    \edef\ieumun@next{\ieumun@current}%
    \typeout{IEUMUN short-page check: section \the\value{ieumun@block},
      pages \ieumun@blockstart--\the\value{page}, last page filled
      \the\pagetotal\space of \the\textheight, level \ieumun@current,
      leading \the\baselineskip, parskip \the\parskip}%
    \ifnum\value{page}>\ieumun@blockstart\relax
      \ifdim\pagetotal>0pt
        \ifdim\pagetotal<\ieumun@shortpage
          \ifnum\ieumun@current<\ieumun@maxlevel\relax
            \edef\ieumun@next{\the\numexpr\ieumun@current+1\relax}%
          \else
            \ClassWarningNoLine{ieumun-guide}{Section \the\value{ieumun@block}
              ends with a nearly empty page (p.~\the\value{page}) even at the
              tightest setting. Shorten or rearrange its text}%
          \fi
        \fi
      \fi
    \fi
    \immediate\write\@auxout{\string\ieumun@savelevel{\the\value{ieumun@block}}{\ieumun@next}}%
  \fi
}
\AtEndDocument{\ieumun@closeblock}
% Read by the build scripts to check that no source note was lost.
\AtEndDocument{\typeout{IEUMUN footnotes: \the\value{footnote}}}

% A section holding only a figure or table leaves \if@nobreak set, which would
% make titlesec skip \sectionbreak for the next section.
\pretocmd{\section}{\par\global\@nobreakfalse}{}{}
\newcommand{\sectionbreak}{%
  \ieumun@closeblock
  \clearpage
  \stepcounter{ieumun@block}%
  \xdef\ieumun@blockstart{\the\value{page}}%
  \ieumun@applylevel{\ieumun@level{\the\value{ieumun@block}}}%
}

\newcommand{\ieumun@headingsetup}{\RaggedRight\hyphenpenalty=10000\exhyphenpenalty=10000}
\newcommand{\ieumun@headingbox}[1]{%
  \parbox[t]{\linewidth}{\ieumun@headingsetup\ieumun@display\fontsize{34}{39}\selectfont#1}%
}

\titleformat{\section}[display]
  {\color{ieumun@text}}
  {{\color{ieumun@accent}\ieumun@thin
    \ifieumun@compacthead\fontsize{44}{44}\else\fontsize{64}{64}\fi\selectfont\thesection}}
  {\ifieumun@compacthead 8pt\else 14pt\fi}
  {\ieumun@headingbox}
  [\vspace{\ifieumun@compacthead 12pt\else 18pt\fi}{\color{ieumun@hairline}\titlerule[0.5pt]}]
\titleformat{name=\section,numberless}[display]
  {\color{ieumun@text}}
  {}
  {0pt}
  {\ieumun@headingbox}
  [\vspace{\ifieumun@compacthead 12pt\else 18pt\fi}{\color{ieumun@hairline}\titlerule[0.5pt]}]
\titlespacing*{\section}{0pt}{0pt}{\ifieumun@compacthead 16pt\else 26pt\fi}

\titleformat{\subsection}[block]
  {\color{ieumun@text}}
  {}
  {0pt}
  {\ieumun@subheadingbox}
\newcommand{\ieumun@subheadingbox}[1]{%
  \parbox[t]{\linewidth}{\ieumun@headingsetup\ieumun@display\fontsize{20}{25}\selectfont#1}%
}
\titlespacing*{\subsection}{0pt}{2.1em}{0.6em}

\titleformat{\subsubsection}[block]
  {\color{ieumun@text}}
  {}
  {0pt}
  {\ieumun@minorheadingbox}
\newcommand{\ieumun@minorheadingbox}[1]{%
  \parbox[t]{\linewidth}{\ieumun@headingsetup\ieumun@bold\fontsize{14}{19}\selectfont#1}%
}
\titlespacing*{\subsubsection}{0pt}{1.6em}{0.35em}

% Fourth heading level: a bold accent line that stays with the text below it.
\newcommand{\minorheading}[1]{%
  \par\addvspace{0.9em}\needspace{3\baselineskip}%
  {\ieumun@headingsetup\ieumun@semibold\color{ieumun@accent}#1\par}%
  \nopagebreak\vspace{0.1em}\nopagebreak
}

%% ---------------------------------------------------------------------------
%% Table of contents
%% ---------------------------------------------------------------------------
% The contents always fit on one page: if the full list is too long it is set
% tighter, and if that is still too long only the sections are listed.
\newif\ifieumun@compacttoc
\titlecontents{section}[0pt]
  {\addvspace{\ifieumun@compacttoc 8pt\else 14pt\fi}\ieumun@semibold
   \ifieumun@compacttoc\fontsize{12}{15}\else\fontsize{13}{17}\fi\selectfont}
  {\makebox[3.2em][l]{\color{ieumun@accent}\ieumun@light\thecontentslabel}}
  {\hspace*{3.2em}}
  {\hfill{\ieumun@medium\color{ieumun@secondary}\thecontentspage}}
  [{\vspace{\ifieumun@compacttoc 4pt\else 6pt\fi}\color{ieumun@hairline}\hrule height 0.4pt}]
\titlecontents{subsection}[3.2em]
  {\addvspace{\ifieumun@compacttoc 2pt\else 5pt\fi}%
   \ifieumun@compacttoc\fontsize{9.5}{12}\else\fontsize{10.5}{14}\fi\selectfont\color{ieumun@secondary}}
  {}
  {}
  {\hfill{\color{ieumun@tertiary}\thecontentspage}}

\newsavebox{\ieumun@tocbox}
\newif\ifieumun@toclong
\newcommand{\ieumun@measuretoc}{%
  \setbox\ieumun@tocbox\vbox{\hsize=\linewidth\makeatletter\@input{\jobname.toc}}%
  \typeout{IEUMUN contents: \the\dimexpr\ht\ieumun@tocbox+\dp\ieumun@tocbox\relax\space
    of \the\dimexpr\textheight-100pt\relax\space available}%
  \ifdim\dimexpr\ht\ieumun@tocbox+\dp\ieumun@tocbox\relax>\dimexpr\textheight-100pt\relax
    \ieumun@toclongtrue
  \else
    \ieumun@toclongfalse
  \fi
}
\newcommand{\ieumun@fittoc}{%
  \IfFileExists{\jobname.toc}{%
    \ieumun@measuretoc
    \ifieumun@toclong
      \ieumun@compacttoctrue
      \parskip=0pt\relax
      \ieumun@measuretoc
      \ifieumun@toclong
        \setcounter{tocdepth}{1}%
        \ieumun@compacttocfalse
        \parskip=0.75em plus 0.2em minus 0.1em\relax
      \fi
    \fi
  }{}%
}

\newcommand{\guidecontents}{%
  \clearpage
  \thispagestyle{plain}%
  {\color{ieumun@accent}\ieumun@kicker{\ieumun@committee}\par}%
  \vspace{6pt}%
  {\ieumun@display\fontsize{32}{36}\selectfont\ieumun@lbl@contents\par}%
  \vspace{18pt}%
  {\color{ieumun@hairline}\hrule height 0.5pt}%
  \vspace{4pt}%
  {\ieumun@fittoc\@starttoc{toc}}%
  \clearpage
}
\renewcommand{\tableofcontents}{\guidecontents}

%% ---------------------------------------------------------------------------
%% Lists
%% ---------------------------------------------------------------------------
\setlist{itemsep=0.35em, topsep=0.5em, parsep=0.2em}
\setlist[itemize,1]{
  label={\color{ieumun@accent}\raisebox{0.2ex}{\rule{0.42em}{0.42em}}},
  leftmargin=1.4em,
}
\setlist[itemize,2]{label={\color{ieumun@secondary}--}, leftmargin=1.2em}
\setlist[enumerate,1]{
  label={\ieumun@semibold\color{ieumun@accent}\arabic*},
  leftmargin=1.6em,
}

%% ---------------------------------------------------------------------------
%% Footnotes (sources)
%% ---------------------------------------------------------------------------
\renewcommand{\@makefnmark}{%
  \hbox{\textsuperscript{\ieumun@semibold\color{ieumun@accent}\@thefnmark}}%
}
\renewcommand{\@makefntext}[1]{%
  \justifying
  \emergencystretch=3em
  \leftskip=1.7em
  \noindent\llap{\makebox[1.7em][l]{\ieumun@semibold\color{ieumun@accent}\@thefnmark}}%
  {\color{ieumun@secondary}#1}%
}
\renewcommand{\footnoterule}{%
  \kern-3pt{\color{ieumun@hairline}\hrule width 0.22\columnwidth height 0.4pt}\kern 8pt%
}
\setlength{\footnotesep}{11pt}
\setlength{\skip\footins}{20pt plus 4pt minus 2pt}
\interfootnotelinepenalty=10000

% Boxes are minipages, which would trap footnotes inside them. Inside boxes,
% \footnote only prints the mark; the texts are emitted after the box ends so
% they join the normal page-bottom sequence.
\newcommand{\ieumun@fnqueue}{}
\newcommand{\ieumun@deferfootnotes}{%
  \gdef\ieumun@fnqueue{}%
  \renewcommand{\footnote}[1]{%
    \stepcounter{footnote}%
    \protected@xdef\@thefnmark{\thefootnote}%
    \@footnotemark
    \xappto\ieumun@fnqueue{%
      \noexpand\footnotetext[\the\value{footnote}]{\unexpanded{##1}}}%
  }%
}
\newcommand{\ieumun@flushfootnotes}{%
  \ieumun@fnqueue
  \gdef\ieumun@fnqueue{}%
}

%% ---------------------------------------------------------------------------
%% Editorial components
%% ---------------------------------------------------------------------------
\newcommand{\ieumun@leadfont}{\fontsize{15}{23}}
\newcommand{\lead}[1]{%
  \ifieumun@compacthead
    #1\par
  \else
    {\ieumun@light\ieumun@leadfont\selectfont\color{ieumun@text}#1\par}%
    \vspace{0.4em}%
  \fi
}

\newcommand{\pullquote}[2][]{%
  \par\vspace{0.9em}%
  \begin{tcolorbox}[
    blank, breakable=false,
    borderline west={2.5pt}{0pt}{ieumun@accent},
    left=16pt, right=0pt, top=2pt, bottom=2pt,
  ]
    \ieumun@deferfootnotes
    {\RaggedRight\ieumun@display\fontsize{20}{27}\selectfont\color{ieumun@text}#2\par}%
    \ifblank{#1}{}{%
      \vspace{8pt}%
      {\color{ieumun@secondary}\ieumun@kicker{#1}\par}%
    }%
  \end{tcolorbox}%
  \ieumun@flushfootnotes
  \vspace{0.6em}%
}

% \begin{chairletter}[Role]{Name} ... \end{chairletter}
\newenvironment{chairletter}[2][]{%
  \par\vspace{0.6em}%
  {\color{ieumun@accent}\ieumun@kicker{\ieumun@lbl@letter}\par}%
  \vspace{4pt}%
  {\ieumun@display\fontsize{22}{26}\selectfont #2\par}%
  \ifblank{#1}{}{\vspace{2pt}{\color{ieumun@secondary}\ieumun@medium #1\par}}%
  \vspace{10pt}%
  {\color{ieumun@hairline}\hrule height 0.4pt}%
  \vspace{6pt}%
  \fontsize{11.5}{\the\ieumun@letterlead}\selectfont
}{%
  \par\vspace{1.4em}%
}

\newcommand{\email}[1]{%
  \href{mailto:#1}{\ieumun@medium\color{ieumun@link}%
    \def\UrlBreaks{\do\.\do\@}\def\UrlBigBreaks{}\nolinkurl{#1}}%
}

% \signoff[Closing line]{Name}: the closing and the name never start a page on
% their own; they always stay with the end of the letter above.
\newcommand{\signoff}[2][]{%
  \par\nopagebreak
  \ifblank{#1}{}{#1\par\nopagebreak}%
  \vspace{0.3em}\nopagebreak
  {\ieumun@semibold #2\par}%
}

% \begin{keypoints}[Title] \item ... \end{keypoints}
\newenvironment{keypoints}[1][Key points]{%
  \begin{tcolorbox}[
    enhanced, breakable=false,
    colback=ieumun@surface, frame hidden,
    arc=12pt, outer arc=12pt,
    left=18pt, right=18pt, top=16pt, bottom=14pt,
    before skip=1.2em, after skip=1.2em,
  ]
  \ieumun@deferfootnotes
  {\color{ieumun@accent}\ieumun@kicker{#1}\par}%
  \vspace{4pt}%
  \begin{itemize}[leftmargin=1.4em, itemsep=0.55em, topsep=0.3em]
}{%
  \end{itemize}%
  \end{tcolorbox}%
  \ieumun@flushfootnotes
}

% Abbreviations: \begin{abbreviations} \abbr{GDP}{Gross Domestic Product} ...
\newenvironment{abbreviations}{%
  \par\vspace{0.4em}%
  {\color{ieumun@text}\hrule height 0.8pt}%
}{%
  \par
}
\newcommand{\abbr}[2]{%
  \par\noindent
  \begin{minipage}[t]{0.3\linewidth}\vspace{0pt}%
    \vspace{9pt}{\ieumun@bold\fontsize{12}{16}\selectfont\color{ieumun@accent}#1}%
  \end{minipage}%
  \begin{minipage}[t]{0.7\linewidth}\vspace{0pt}%
    \vspace{9pt}\RaggedRight{\fontsize{10.5}{16}\selectfont #2}%
  \end{minipage}\par
  \vspace{9pt}%
  {\color{ieumun@hairline}\hrule height 0.4pt}%
}

% \guidefig[caption]{path}[width as a fraction of the text width]
\NewDocumentCommand{\guidefig}{O{} m O{1}}{%
  \begin{figure}[H]
    \centering
    \includegraphics[width=#3\linewidth,height=0.45\textheight,keepaspectratio]{#2}%
    \ifblank{#1}{}{\caption{#1}}%
  \end{figure}%
}
\DeclareCaptionFont{ieumunsecondary}{\color{ieumun@secondary}}
\DeclareCaptionFont{ieumunaccent}{\color{ieumun@accent}}
\captionsetup{
  font={footnotesize,ieumunsecondary},
  labelfont={ieumunaccent,bf},
  labelsep=period,
  justification=raggedright,
  singlelinecheck=false,
  skip=8pt,
}

% Simple bibliography typed by hand (e.g. copied from a Word document)
\newenvironment{referencelist}{%
  \begin{list}{}{%
    \setlength{\leftmargin}{\bibhang}%
    \setlength{\itemindent}{-\bibhang}%
    \setlength{\itemsep}{\bibitemsep}%
    \setlength{\parsep}{0pt}%
  }\bibfont
}{%
  \end{list}%
}
\newcommand{\refitem}{\item[]}

\newcommand{\unnumberedsection}[1]{%
  \section*{#1}%
  \addcontentsline{toc}{section}{#1}%
  \markboth{#1}{}%
}
\defbibheading{bibliography}[\ieumun@lbl@references]{\unnumberedsection{#1}}

% \begin{guidetable}[column spec]{number of columns} a & b \\ \midrule c & d \\ \end{guidetable}
% Tables may run across pages. The optional spec sets relative widths with
% Y{factor} columns, e.g. [Y{0.6}Y{1.4}] (factors add up to the column count).
\newcolumntype{Y}[1]{>{\RaggedRight\arraybackslash\hsize=#1\hsize}X}
\RequirePackage{xltabular}
\newenvironment{guidetable}[2][]{%
  \par\vspace{0.3em}\small
  \renewcommand{\arraystretch}{1.35}%
  \setlength{\LTpre}{0.3em}\setlength{\LTpost}{0.6em}%
  \ifblank{#1}%
    {\def\ieumun@tablespec{*{#2}{>{\RaggedRight\arraybackslash}X}}}%
    {\def\ieumun@tablespec{#1}}%
  \expandafter\xltabular\expandafter{\expandafter\linewidth\expandafter}\expandafter{\ieumun@tablespec}%
  \toprule
}{%
  \bottomrule
  \endxltabular
  \par
}
\setlength{\heavyrulewidth}{0.8pt}
\setlength{\lightrulewidth}{0.4pt}
\AtBeginDocument{\arrayrulecolor{ieumun@hairline}}
\RequirePackage{colortbl}

\newcommand{\todo}[1]{%
  \par\vspace{0.8em}%
  \begin{tcolorbox}[
    enhanced, colback=white, colframe=ieumun@hairline,
    boxrule=0.6pt, arc=10pt, borderline={0.6pt}{0pt}{ieumun@hairline,dashed},
    frame hidden, left=16pt, right=16pt, top=12pt, bottom=12pt,
  ]
    {\color{ieumun@secondary}\ieumun@kicker{To be completed}\par}%
    \vspace{3pt}{\small\color{ieumun@secondary}#1\par}%
  \end{tcolorbox}%
}

%% ---------------------------------------------------------------------------
%% Cover
%% ---------------------------------------------------------------------------
\RequirePackage{ieumun-cover}

\endinput

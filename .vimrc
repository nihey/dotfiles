" Vundle setup
set nocompatible
filetype off
set rtp+=~/.vim/bundle/Vundle.vim
call vundle#begin()
Plugin 'wakatime/vim-wakatime'
Plugin 'git://github.com/gmarik/Vundle.vim.git'
Plugin 'git://github.com/terryma/vim-multiple-cursors'
Plugin 'git://github.com/itchyny/lightline.vim'
Plugin 'git://github.com/sjl/gundo.vim.git'
Plugin 'git://github.com/kevinw/pyflakes-vim.git'
Plugin 'git://github.com/mxw/vim-jsx.git'
Plugin 'git://github.com/nanotech/jellybeans.vim.git'
call vundle#end()
filetype plugin indent on

" General Settings
colorscheme jellybeans      " JellyBeans colorscheme
syntax on                   " Enable syntax highlighting
set hls                     " Highlight search
set number                  " Show line numbers
set fo=tcq                  " FormatOption - (textwidth, comments, allow gq)
set ts=4                    " TabStop - tab is shown with 4 columns
set sw=4                    " ShiftWidth - 4 space identation
set sts=4                   " SoftTabStop Number of spaces a tab counts
set ai                      " AutoIndenting
set wrapmargin=2            " WrapMargin wraps text before reaching 2 columns away from window border
set ruler                   " Show cursor position (lower left side)
set tildeop                 " ~ behaves like and operator
set visualbell
set shell=/bin/bash         " Which shell will be used on shell command
set showcmd                 " Show commands on the last line
set textwidth=79            " Wrap text in 79 columns
set colorcolumn=79          " Highlight the 79th column
set mouse=n                 " Enables use of the mouse
set incsearch               " Show where a matched pattern is
set title                   " Show file that is been edited
set encoding=utf-8          " Encoding
set termencoding=utf-8      " Terminal encoding
set laststatus=2            " When the last window will have a status line
set noswapfile              " Do not create .sw* files
set smartcase               " Case insensitive search for lower case characters
let mapleader=' '           " Set which key is the map leader
set t_Co=256                " Use 256 colors
highlight ColorColumn ctermbg=235 guibg=#2c2d27

" Highlight trailling whitespaces
set list listchars=tab:\|_,trail:$
set listchars=tab:>\ ,trail:-,extends:>,precedes:<,nbsp:+
highlight SpecialKey ctermfg=Red ctermbg=Yellow guibg=Yellow
autocmd BufEnter *.diff highlight SpecialKey ctermfg=red ctermbg=red guibg=black
highlight clear SpellBad
highlight link SpellBad ErrorMsg

" Remove trailling whitespaces when saving
autocmd BufWritePre *.* :%s/\s\+$//e

" Makefile (tabs only)
autocmd BufEnter {Makefile,makefile}* set noexpandtab
autocmd BufEnter {Makefile,makefile}* set nolist

" PostgreSQL editor
autocmd BufEnter psql.edit* set syntax=sql
autocmd BufEnter psql.edit* set nolist

" 4 Spaced -> Python, HonScript
autocmd BufEnter *.{py,hon} set sts=4
autocmd BufEnter *.{py,hon} set ts=4
autocmd BufEnter *.{py,hon} set sw=4

" 2 Spaced -> JavaScript, CSS, Less, Sass, HTML, Handlebars
autocmd BufEnter *.{js*,css,less,sass,s?html*,hbs} set sts=2
autocmd BufEnter *.{js*,css,less,sass,s?html*,hbs} set ts=2
autocmd BufEnter *.{js*,css,less,sass,s?html*,hbs} set sw=2

" TextWrap, with 79 limit -> Python JavaScript, CSS, Less, Sass
autocmd BufEnter *.{py,js*,css,less,sass} set wrap
autocmd BufEnter *.{py,js*,css,less,sass} set textwidth=79

" NoTextWrap, without 79 limit -> HTML, Handlebars, HonScript
autocmd BufEnter *.{s?html*,hbs,hon} set nowrap
autocmd BufEnter *.{s?html*,hbs,hon} set textwidth=0

" CSS Syntax -> Less, Sass
autocmd BufEnter *.{less,sass} set syntax=css

" Shell Syntax -> HonScript
autocmd BufEnter *.hon set syntax=sh

" Gundo Mapping
nnoremap <F9> :GundoToggle<CR>

" Enable sudow
cnoremap sudow w !sudo tee % >/dev/null
set expandtab               " Use correct number of spaces on tabbing with > <

#! /usr/bin/python
# -*- coding: utf-8 -*-
# 
# $Id: first.py 9197 2008-09-01 14:26:47Z kandal $
#
import locale
locale.setlocale(locale.LC_ALL, 'nb_NO.UTF-8')

import sys
import reportlab.rl_config

from time import *
from StringIO import StringIO

from reportlab.lib.colors import red, black, navy, white, green
from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER
from reportlab.lib.enums import TA_JUSTIFY
from reportlab.lib.pagesizes import A4, letter
from reportlab.lib.randomtext import randomText
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm, inch

from reportlab.pdfgen import canvas

from reportlab.platypus import Indenter, XPreformatted, TableStyle
from reportlab.platypus import Paragraph, SimpleDocTemplate, XBox
from reportlab.platypus import BaseDocTemplate, PageBreak, Table

#from reportlab.test import unittest
#from reportlab.test.utils import makeSuiteForClasses, outputfile
#from reportlab.test.utils import printLocation

class CerebrumUserSchema:
    
    def __init__(self, lastname,
                 firstname,
                 email,
                 username,
                 passwd,
                 birthdate,
                 studyprogram,
                 year,
                 faculty,
                 department,
                 lang = 'no'):
        self.lastname = lastname
        self.firstname = firstname
        self.email = email
        self.username = username
        self.passwd = passwd
        self.birthdate = birthdate
        self.studyprogram = studyprogram
        self.year = year
        self.faculty = faculty
        self.department = department
        self.thelang = lang
        if self.thelang == 'en':
            locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')
            import userschema_en as langFile
        else:
            import userschema_no as langFile
        self.lang = langFile
        ## try to split facultyname at position 30
        ## if it is longer than 30 chars
        self.maxFacultyLen = 30
        ## 
        self.paperSize = A4
        ##
        self.width, self.height = self.paperSize
        ## from the left edge of paper
        self.leftMargin = 2 * cm
        ## from the right edge of paper
        self.rightMargin = 1 * cm
        ## where to place the institution's name
        ## from the top edge of paper
        self.topMargin = 3 * cm
        ## where to place the person's name
        ## from the top edge of paper
        self.nameMargin = 6 *cm
        ## where to place the department's name
        ## from the top edge of paper
        self.departmentMargin = 6.5 * cm
        ## where to place the date
        ## from the top edge of paper
        self.dateMargin = 7 * cm
        ## where to place the institution- and
        ## faculty-name.
        self.topTextStart = self.height - self.topMargin
        ## fontsize for institution- and faculty-name
        self.topTextSize = 14
        ## where to place the page-number from
        ## the bottom edge
        self.pageNumberPosX = (self.width/2)
        ## page-number is centered on the page
        self.pageNumberPosY = 1 * cm
        self.bottomMargin = 4 * cm
        self.city = 'Trondheim'
        ## day of month, full month-name, and YYYY
        self.dateAndTimeFormat = self.city + ', %d. %B, %Y'
        self.boldTextFont = 'Times-Bold'
        self.normalTextFont = 'Times-Roman'
        self.normalTextSize = 12
        self.normalTextSty = ParagraphStyle('normalText',
                                            fontName = self.normalTextFont,
                                            firstLineIndent = 0,
                                            fontSize = self.normalTextSize,
                                            leftIndent = 0,
                                            leading = 12,
                                            align = TA_LEFT,
                                            spaceBefore = 0,
                                            spaceAfter = 12,
                                            wordWrap = True)
        self.bulletText = '\xe2\x80\xa2'
        self.bulletSty = ParagraphStyle('bullet',
                                        fontName = self.normalTextFont,
                                        leading = 12,
                                        fontSize = self.normalTextSize,
                                        leftIndent = 10,
                                        spaceAfter = 12,
                                        bulletIndent = 0,
                                        bulletFontName = self.normalTextFont,
                                        bulletFontSize =
                                        self.normalTextSize)
        self.titleSty = ParagraphStyle('title',
                                       fontName = self.boldTextFont,
                                       fontSize = self.normalTextSize,
                                       leading = 12,
                                       alignment = TA_LEFT,
                                       spaceBefore = 0,
                                       spaceAfter = 12,
                                       wordWrap = True)

    def getFormattedDate(self):
        return strftime(self.dateAndTimeFormat, localtime())
    
    def splitString(self, str, splitChar, trySplitAt):
        pieces = []
        rest = str
        ## how many times must we split the string
        splitIn = len(str)/trySplitAt
        if splitIn > 0:
            ## where to start searching for a split-char
            startAt = len(rest)/(splitIn + 1)
            ## start searching for a space and split there
            idx = rest.find(splitChar, startAt)
            while idx > -1:
                ## first slice into the list
                pieces.append(rest[0:idx])
                ## save the rest
                rest = rest[(idx + 1):]
                ## and try to find where to do the
                ## next split
                idx = rest.find(splitChar, startAt)
        ## append what is left
        pieces.append(rest)
        ## print pieces
        return pieces
        
    def makeHead(self, canvas, doc):
        canvas.saveState()
        ## institution-name
        canvas.setFont(self.boldTextFont, self.topTextSize)
        institutionHashes = self.splitString(self.lang.institutionName(),
                                             ' ',
                                             self.maxFacultyLen)
        for i in range(0, len(institutionHashes)):
             canvas.drawString(self.leftMargin,
                                    self.topTextStart -
                                    (self.topTextSize * i),
                                    institutionHashes[i])
                                    
        canvas.drawString(self.leftMargin,
                          self.topTextStart - (self.topTextSize * len(institutionHashes)), 
                          self.lang.institutionAcronym())

        facultyHashes = self.splitString(self.faculty, ' ', self.maxFacultyLen)
        for i in range(0, len(facultyHashes)):
            canvas.drawRightString(self.width - self.rightMargin,
                                   self.topTextStart - (self.topTextSize * i),
                                   facultyHashes[i])
        ## page-number
        canvas.setFont(self.normalTextFont, 10)
        canvas.drawString(self.pageNumberPosX,
                          self.pageNumberPosY,
                          "%d" % doc.page)
        ## person's name
        canvas.setFont(self.normalTextFont, self.normalTextSize)
        canvas.drawString(self.leftMargin, self.height - (6 *cm),
                          self.lastname + ', ' + self.firstname)
        ## department-name
        canvas.setFont(self.boldTextFont, 10)
        canvas.drawRightString(self.width - self.rightMargin,
                               self.height - (6.5 *cm),
                               self.department)
        ## date
        canvas.setFont(self.normalTextFont, 10)
        canvas.drawRightString(self.width - self.rightMargin,
                               self.height - (7 * cm),
                               self.getFormattedDate())
        canvas.restoreState()

    def makeFirstPage(self, canvas, doc):
        self.makeHead(canvas, doc)
        canvas.saveState()

        dateLinePosY = self.bottomMargin + (6 * cm)
        signatureLinePosY = dateLinePosY
        dateLineLength = 4 *cm
        signatureLinePosX = self.leftMargin + (6 * cm)
        signatureLineLength = 10 *cm

        ## date-line
        canvas.line(self.leftMargin,
                    dateLinePosY,
                    self.leftMargin + dateLineLength,
                    dateLinePosY)
        ## signature-line
        canvas.line(signatureLinePosX,
                    signatureLinePosY,
                    signatureLinePosX + signatureLineLength,
                    signatureLinePosY)

        textPaddingTop = 0.5 * cm
        canvas.setFont(self.boldTextFont, 10)
        ## text under date-line
        canvas.drawString(self.leftMargin,
                          dateLinePosY - textPaddingTop,
                          self.lang.dateText())
        ## text under signature-line
        canvas.drawString(signatureLinePosX,
                          signatureLinePosY - textPaddingTop,
                          self.lang.signatureText())

        # draw the horizontal lines for the table
        cellHeight = 0.9 * cm
        numberOfRows = 4
        ## space between the 2 lines that make the frames
        ## around the table
        doubleFrameSpace = 2
        for i in range(0, (numberOfRows + 1)):
            canvas.line(self.leftMargin,
                        self.bottomMargin + (i * cellHeight),
                        self.width - self.rightMargin,
                        self.bottomMargin + (i * cellHeight))
            if i == 0:
                # frame line is double
                canvas.line(self.leftMargin,
                            self.bottomMargin + (i * cellHeight) -
                            doubleFrameSpace,
                            self.width - self.rightMargin,
                            self.bottomMargin + (i * cellHeight) -
                            doubleFrameSpace)
            if i == numberOfRows:
                # top frame is double
                canvas.line(self.leftMargin,
                            self.bottomMargin + (i * cellHeight) +
                            doubleFrameSpace,
                            self.width - self.rightMargin,
                            self.bottomMargin + (i * cellHeight) +
                            doubleFrameSpace) 
        ## left frames of the table
        ## from top to down
        ## left outer frame
        canvas.line(self.leftMargin,
                    self.bottomMargin + (numberOfRows * cellHeight),
                    self.leftMargin,
                    self.bottomMargin)
        ## left inner frame
        canvas.line(self.leftMargin  + doubleFrameSpace,
                    self.bottomMargin + (numberOfRows * cellHeight),
                    self.leftMargin + doubleFrameSpace,
                    self.bottomMargin)
        ## right frame for the table
        ## from top to bottom
        ## right outer frame
        canvas.line(self.width - self.rightMargin,
                    self.bottomMargin + (numberOfRows * cellHeight),
                    self.width - self.rightMargin,
                    self.bottomMargin)
        ## right inner frame
        canvas.line(self.width - self.rightMargin - doubleFrameSpace,
                    self.bottomMargin + (numberOfRows * cellHeight),
                    self.width - self.rightMargin - doubleFrameSpace,
                    self.bottomMargin)

        firstColumnWidth = 3 * cm
        secondColumnWidth = 6 *cm
        thirdColumnWidth = 3 * cm
        ## right frame for first column
        ## from top to bottom
        canvas.line(self.leftMargin + firstColumnWidth,
                    self.bottomMargin + (numberOfRows * cellHeight),
                    self.leftMargin + firstColumnWidth,
                    self.bottomMargin)
        ## right frame for column 2, and 3. and 4. row
        ## from top to bottom
        canvas.line(self.leftMargin + firstColumnWidth + secondColumnWidth,
                    self.bottomMargin + (2 * cellHeight),
                    self.leftMargin + firstColumnWidth + secondColumnWidth,
                    self.bottomMargin + cellHeight)
        ## right frame for column 3, and 3 and 4. row
        ## from top to bottom
        canvas.line(self.leftMargin + firstColumnWidth +
                    secondColumnWidth + thirdColumnWidth,
                    self.bottomMargin + (2 * cellHeight),
                    self.leftMargin + firstColumnWidth +
                    secondColumnWidth + thirdColumnWidth,
                    self.bottomMargin + cellHeight)
        
        ## texts in the first column
        canvas.setFont(self.boldTextFont, self.normalTextSize)
        rowTexts = [self.lang.facultyText(),
                    self.lang.usernameText(),
                    self.lang.emailText(),
                    self.lang.nameText()]
        ## padding of text in the cells
        textPaddingBottom = 3
        textPaddingLeft = 5
        start = self.bottomMargin + textPaddingBottom
        for i in range(0, numberOfRows):
            canvas.drawString(self.leftMargin + textPaddingLeft,
                              start + (i * cellHeight),
                              rowTexts[i])
            
        # text in 3. column
        canvas.drawString(self.leftMargin + firstColumnWidth +
                          secondColumnWidth + textPaddingLeft,
                          start +  cellHeight,
                          self.lang.birthdateText())

        canvas.setFont(self.normalTextFont, self.normalTextSize)        
        ## the data in 2. column
        rowData = [self.faculty,
                   self.username,
                   self.email,
                   self.lastname + ', ' + self.firstname]
        for i in range(0, numberOfRows):
            if rowData[i]:
                canvas.drawString(self.leftMargin + firstColumnWidth +
                                  textPaddingLeft ,
                                  start + (i * cellHeight),
                                  rowData[i])
        # data in 4. column
        if self.birthdate:
            canvas.drawString(self.leftMargin + firstColumnWidth +
                              secondColumnWidth + thirdColumnWidth +
                              textPaddingLeft,
                              start + cellHeight,
                              self.birthdate)
        canvas.restoreState()

    def makeLastPage(self, canvas, doc):
        self.makeHead(canvas, doc)
        canvas.saveState()
        canvas.setFont(self.normalTextFont, self.normalTextSize)
        canvas.drawString(self.leftMargin,
                          self.bottomMargin + (2.5 * cm),
                          self.lang.greetingText())
        canvas.drawString(self.leftMargin,
                          self.bottomMargin + (0.5 * cm),
                          self.lang.itDirector())
        canvas.drawString(self.leftMargin,
                          self.bottomMargin,
                          self.lang.positionText())
        canvas.restoreState()

    def makeLotsOfText(self):
        t = 'dille dille dille '
        for i in range(0, 5):
            t = t + t
        return t

    def build(self):
        templateTopMargin = 7.5 * cm
        templateBottomMargin = 7 * cm
        output = StringIO()
        template = SimpleDocTemplate(output,
                                     pagesize = self.paperSize,
                                     showBoundary = 0,
                                     leftMargin = self.leftMargin,
                                     rightMargin = self.rightMargin,
                                     topMargin = templateTopMargin,
                                     bottomMargin = templateBottomMargin,
                                     allowSplitting = 1,
                                     title = 'CerebrumUserSchema',
                                     author = 'first.py')
                                            
        allLines = []
       
        ## underline the text by <u>
        allLines.append(Paragraph(self.lang.pageOneTitle(), self.titleSty))

        allLines.append(Paragraph(self.lang.text01(), self.normalTextSty))

        allLines.append(Paragraph(self.lang.text11(), self.normalTextSty))
        
        urlSty = ParagraphStyle('url',
                                fontName = self.normalTextFont,
                                firstLineIndent = 0,
                                leftIndent = 20,
                                fontSize = self.normalTextSize,
                                leading = 12,
                                spaceBefore = 0,
                                spaceAfter = 12)

        allLines.append(Paragraph(self.lang.text12(), urlSty))

        allLines.append(Paragraph(self.lang.text13(), self.normalTextSty))

        declarationSty = ParagraphStyle('declaration',
                                       fontName = self.boldTextFont,
                                       fontSize = 16,
                                       leftIndent = 6 *cm,
                                       leading = 12,
                                       align = TA_CENTER,
                                       spaceBefore = 32,
                                       spaceAfter = 12,
                                       wordWrap = True)
        allLines.append(Paragraph(self.lang.declarationText(), declarationSty))

        allLines.append(Paragraph(self.lang.bullet10(), self.bulletSty,
                                  bulletText=self.bulletText))

        allLines.append(Paragraph(self.lang.bullet11(), self.bulletSty,
                                  bulletText=self.bulletText))
        ## flush the 1. page
        allLines.append(PageBreak())

        allLines.append(Paragraph(self.lang.pageTwoTitle(), self.titleSty))
        
        allLines.append(Paragraph(self.lang.text20(), self.normalTextSty))
        
        tableData = ([self.lang.usernameText(), self.username],
                     [self.lang.passwordText(), self.passwd],
                     [self.lang.emailAddressText(), self.email])
        tableStyleList = [
            ('FONT', (0,0), (0,-1), self.boldTextFont),
            ('FONTSIZE', (0,0), (-1,-1), self.normalTextSize)
            ]
        ## force the table to the left
        colWidths = (4 * cm, 13 * cm)
        allLines.append(Table(tableData, colWidths=colWidths,
                     style=TableStyle(tableStyleList)))

        ## really silly, a dummy paragraph to get vertical space
        ## between the table and the following text
        allLines.append(Paragraph('', self.normalTextSty))

        allLines.append(Paragraph(self.lang.bullet20(), self.bulletSty,
                     bulletText = self.bulletText))

        allLines.append(Paragraph(self.lang.bullet21(), self.bulletSty,
                                  bulletText = self.bulletText))

        allLines.append(Paragraph(self.lang.bullet22(), self.bulletSty,
                                  bulletText = self.bulletText))

        allLines.append(Paragraph(self.lang.text21(), self.normalTextSty))

        allLines.append(Paragraph(self.lang.bullet23(), self.bulletSty,
                                  bulletText = self.bulletText)) 

        allLines.append(Paragraph(self.lang.text22(), self.normalTextSty))

        allLines.append(Paragraph(self.lang.text23(), self.normalTextSty))

        allLines.append(Paragraph(self.lang.text24(), self.normalTextSty))

        template.build(allLines, onFirstPage=self.makeFirstPage,
                       onLaterPages=self.makeLastPage)
        pdf = output.getvalue()
        output.close()
        return pdf

def main(args):
    lastname = 'Haugen'
    firstname = 'Odd Arne'
    email = 'Odd.Haugen@ntnu.no'
    username = 'oah'
    passwd = None
    birthdate= '17.05.1954'
    studyprogram = 'siv.ing'
    year = '1976'
    faculty = 'Direktør for organisasjon og informasjon'
    department = 'IT-avdelingen'
    schema = CerebrumUserSchema( lastname,
                                 firstname,
                                 email,
                                 username,
                                 passwd,
                                 birthdate,
                                 studyprogram,
                                 year,
                                 faculty,
                                 department,
                                 lang = 'en')
    pdf = schema.build()
    outFile = open("first.pdf", "w")
    outFile.write(pdf)
    outFile.close()

if __name__ == '__main__':
    main(sys.argv[1:])

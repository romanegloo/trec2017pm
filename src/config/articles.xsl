<xsl:stylesheet version='1.0' xmlns:xsl='http://www.w3.org/1999/XSL/Transform'>
    <xsl:output media-type="text/xml" method="xml" indent="yes"/>
    <xsl:template match="/">
        <add>
            <xsl:for-each select="PubmedArticleSet/PubmedArticle">
                <doc>
                    <field name="id">
                        <xsl:value-of select="MedlineCitation/PMID"/>
                    </field>
                    <xsl:apply-templates select="MedlineCitation/Article"/>
                    <xsl:apply-templates select="MedlineCitation/MeshHeadingList"/>
                    <xsl:apply-templates select="MedlineCitation/ChemicalList"/>
                </doc>
            </xsl:for-each>
        </add>
    </xsl:template>

    <xsl:template match="Article">
        <field name="journal-title"> <xsl:value-of select="Journal/Title"/> </field>
        <field name="subject"> <xsl:value-of select="ArticleTitle"/> </field>
        <field name="abstract"> <xsl:value-of select="Abstract/AbstractText"/> </field>
    </xsl:template>

    <xsl:template match="MeshHeadingList">
        <xsl:for-each select="MeshHeading/DescriptorName">
            <field name="meshHeading"> <xsl:value-of select="."/> </field>
            <field name="MeshHeading_UI"> <xsl:value-of select="@UI"/> </field>
        </xsl:for-each>
    </xsl:template>

    <xsl:template match="ChemicalList">
        <xsl:for-each select="Chemical">
            <field name="Chemical">
                <xsl:value-of select="NameOfSubstance"/>
            </field>
            <field name="Chemical_UI">
                <xsl:value-of select="NameOfSubstance/@UI"/>
            </field>
        </xsl:for-each>
    </xsl:template>
</xsl:stylesheet>
